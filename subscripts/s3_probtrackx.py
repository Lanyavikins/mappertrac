#!/usr/bin/env python3
from subscripts.config import executor_labels
from subscripts.utilities import write_start
from parsl.app.app import python_app

@python_app(executors=executor_labels)
def s3_1_probtrackx(sdir, a, b, use_gpu, stdout, container):
    from subscripts.utilities import run,smart_remove,smart_mkdir,write
    from os.path import join,exists
    from shutil import copyfile
    EDI_allvols = join(sdir,"EDI","allvols")
    a_file = join(EDI_allvols, a + "_s2fa.nii.gz")
    b_file = join(EDI_allvols, b + "_s2fa.nii.gz")
    a_to_b = "{}to{}".format(a, b)
    a_to_b_formatted = "{}_s2fato{}_s2fa.nii.gz".format(a,b)
    pbtk_dir = join(sdir,"EDI","PBTKresults")
    a_to_b_file = join(pbtk_dir,a_to_b_formatted)
    tmp = join(sdir, "tmp", a_to_b)
    waypoints = join(tmp,"tmp_waypoint.txt".format(a_to_b))
    exclusion = join(tmp,"tmp_exclusion.nii.gz".format(a_to_b))
    termination = join(tmp,"tmp_termination.nii.gz".format(a_to_b))
    bs = join(sdir,"bs.nii.gz")
    allvoxelscortsubcort = join(sdir,"allvoxelscortsubcort.nii.gz")
    terminationmask = join(sdir,"terminationmask.nii.gz")
    bedpostxResults = join(sdir,"bedpostx_b1000.bedpostX")
    merged = join(bedpostxResults,"merged")
    nodif_brain_mask = join(bedpostxResults,"nodif_brain_mask.nii.gz")
    if not exists(a_file) or not exists(b_file):
        write(stdout, "Error: Both Freesurfer regions must exist: {} and {}".format(a_file, b_file))
        return
    smart_remove(a_to_b_file)
    smart_remove(tmp)
    smart_mkdir(tmp)
    smart_mkdir(pbtk_dir)
    write(stdout, "Running subproc: {}".format(a_to_b))
    run("fslmaths {} -sub {} {}".format(allvoxelscortsubcort, a_file, exclusion), stdout, container)
    run("fslmaths {} -sub {} {}".format(exclusion, b_file, exclusion), stdout, container)
    run("fslmaths {} -add {} {}".format(exclusion, bs, exclusion), stdout, container)
    run("fslmaths {} -add {} {}".format(terminationmask, b_file, termination), stdout, container)
    with open((waypoints),"w") as f:
        f.write(b_file + "\n")
    arguments = (" -x {} ".format(a_file) +
        " --pd -l -c 0.2 -S 2000 --steplength=0.5 -P 1000" +
        " --waypoints={} --avoid={} --stop={}".format(waypoints, exclusion, termination) +
        " --forcedir --opd" +
        " -s {}".format(merged) +
        " -m {}".format(nodif_brain_mask) +
        " --dir={}".format(tmp) +
        " --out={}".format(a_to_b_formatted) +
        " --omatrix1" # output seed-to-seed sparse connectivity matrix
        )
    if use_gpu:
        write(stdout, "Running Probtrackx with GPU")
        run("probtrackx2_gpu" + arguments, stdout, container)
    else:
        write(stdout, "Running Probtrackx without GPU")
        run("probtrackx2" + arguments, stdout, container)
    copyfile(join(tmp, a_to_b_formatted), a_to_b_file)
    smart_remove(tmp)

@python_app(executors=executor_labels)
def s3_2_complete(sdir, stdout, checksum, inputs=[]):
    from subscripts.utilities import write_finish,write_checkpoint
    write_finish(stdout, "s3_probtrackx")
    write_checkpoint(sdir, "s3", checksum)

def create_job(sdir, edge_list, use_gpu, stdout, container, checksum):
    s3_1_futures = []
    processed_edges = []
    write_start(stdout, "s3_probtrackx")
    with open(edge_list) as f:
        for edge in f.readlines():
            if edge.isspace():
                continue
            a, b = edge.replace("_s2fa", "").strip().split(',', 1)
            a_to_b = "{}to{}".format(a, b)
            b_to_a = "{}to{}".format(b, a)
            if a_to_b not in processed_edges and b_to_a not in processed_edges:
                s3_1_futures.append(s3_1_probtrackx(sdir, a, b, use_gpu, stdout, container))
                s3_1_futures.append(s3_1_probtrackx(sdir, b, a, use_gpu, stdout, container))
                processed_edges.append(a_to_b)
                processed_edges.append(b_to_a)
    return s3_2_complete(sdir, stdout, checksum, inputs=s3_1_futures)
