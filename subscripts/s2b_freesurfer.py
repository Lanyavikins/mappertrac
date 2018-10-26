#!/usr/bin/env python3
from subscripts.config import executor_labels
from parsl.app.app import python_app

@python_app(executors=executor_labels)
def s2b_1_recon_all(sdir, use_gpu, num_cores, stdout, container, checksum, force):
    from subscripts.utilities import run,smart_mkdir,smart_remove,write,write_start,write_checkpoint,read_checkpoint
    from os import environ
    from os.path import exists,join,split,basename
    if read_checkpoint(sdir, "s2b_1_recon_all", checksum) and not force:
        write(stdout, "Already ran recon-all on {}. Use --force to re-compute.".format(basename(sdir)))
        return
    write_start(stdout, "s2b_freesurfer")
    T1 = join(sdir,"T1.nii.gz")
    mri_out = join(sdir,"mri","orig","001.mgz")
    subject = split(sdir)[1]
    environ['SUBJECTS_DIR'] = split(sdir)[0]
    smart_mkdir(join(sdir,"mri"))
    smart_mkdir(join(sdir,"mri","orig"))
    run("mri_convert {} {}".format(T1,mri_out), stdout, container)

    if use_gpu:
        if environ and 'CUDA_5_LIB_DIR' not in environ:
            write(stdout, "Error: Environment variable CUDA_5_LIB_DIR not set. Please install CUDA 5 to use Freesurfer GPU functions.")
            return
        environ['CUDA_LIB_DIR'] = environ['CUDA_5_LIB_DIR']
        environ['LD_LIBRARY_PATH'] = "{}:{}".format(environ['CUDA_LIB_DIR'],environ['LD_LIBRARY_PATH'])
        write(stdout, "Running Freesurfer with GPU and {} cores".format(num_cores))
        run("recon-all -s {} -all -no-isrunning -use-gpu -parallel -openmp {}".format(subject, num_cores), stdout, container)
    elif num_cores > 1:
        write(stdout, "Running Freesurfer with {} cores".format(num_cores))
        run("recon-all -s {} -all -no-isrunning -parallel -openmp {}".format(subject, num_cores), stdout, container)
    else:
        write(stdout, "Running Freesurfer with a single core")
        run("recon-all -s {} -all -no-isrunning".format(subject), stdout, container)
    write_checkpoint(sdir, "s2b_1_recon_all", checksum)

@python_app(executors=executor_labels)
def s2b_2_process_vols(sdir, stdout, container, checksum, inputs=[]):
    from subscripts.utilities import run,smart_mkdir,smart_remove,write,write_finish,write_checkpoint
    from subscripts.maskseeds import maskseeds,saveallvoxels
    from os.path import exists,join,split,splitext
    from os import environ
    from shutil import copy
    from glob import glob
    T1 = join(sdir,"T1.nii.gz")
    subject = split(sdir)[1]
    environ['SUBJECTS_DIR'] = split(sdir)[0]
    FA = join(sdir,"FA.nii.gz")
    aseg = join(sdir,"aseg.nii.gz")
    bs = join(sdir,"bs.nii.gz")
    FA2T1 = join(sdir,"FA2T1.mat")
    T12FA = join(sdir,"T12FA.mat")
    cort_label_dir = join(sdir,"label_cortical")
    cort_vol_dir = join(sdir,"volumes_cortical")
    cort_vol_dir_out = cort_vol_dir + "_s2fa"
    subcort_vol_dir = join(sdir,"volumes_subcortical")
    subcort_vol_dir_out = subcort_vol_dir + "_s2fa"
    terminationmask = join(sdir,"terminationmask.nii.gz")
    allvoxelscortsubcort = join(sdir,"allvoxelscortsubcort.nii.gz")
    intersection = join(sdir,"intersection.nii.gz")
    exclusion_bsplusthalami = join(sdir,"exclusion_bsplusthalami.nii.gz")
    subcortical_index = join("lists","subcorticalIndex.txt")
    EDI = join(sdir,"EDI")
    EDI_allvols = join(EDI,"allvols")
    smart_mkdir(cort_label_dir)
    smart_mkdir(cort_vol_dir)
    smart_mkdir(subcort_vol_dir)
    smart_mkdir(cort_vol_dir_out)
    smart_mkdir(subcort_vol_dir_out)
    smart_mkdir(EDI)
    smart_mkdir(EDI_allvols)
    run("mri_convert {} {} ".format(join(sdir,"mri","brain.mgz"),T1), stdout, container)
    run("flirt -in {} -ref {} -omat {}".format(FA,T1,FA2T1), stdout, container)
    run("convert_xfm -omat {} -inverse {}".format(T12FA,FA2T1), stdout, container)
    run("mri_annotation2label --subject {} --hemi rh --annotation aparc --outdir {}".format(subject, cort_label_dir), stdout, container)
    run("mri_annotation2label --subject {} --hemi lh --annotation aparc --outdir {}".format(subject, cort_label_dir), stdout, container)

    for label in glob(join(cort_label_dir,"*.label")):
        vol_file = join(cort_vol_dir, splitext(split(label)[1])[0] + ".nii.gz")
        run("mri_label2vol --label {} --temp {} --identity --o {}".format(label,T1,vol_file), stdout, container)

    run("mri_convert {} {}".format(join(sdir,"mri","aseg.mgz"),aseg), stdout, container)
    for line in open(subcortical_index,"r").readlines():
        num = line.split(":")[0].lstrip().rstrip()
        area = line.split(":")[1].lstrip().rstrip()
        area_out = join(subcort_vol_dir,area + ".nii.gz")
        write(stdout, "Processing " + area + ".nii.gz")
        run("fslmaths {} -uthr {} -thr {} -bin {}".format(aseg,num,num,area_out), stdout, container)

    for volume in glob(join(cort_vol_dir,"*.nii.gz")):
        out_vol = join(cort_vol_dir_out,splitext(splitext(split(volume)[1])[0])[0] + "_s2fa.nii.gz")
        write(stdout, "Processing {} -> {}".format(split(volume)[1], split(out_vol)[1]))
        run("flirt -in {} -ref {} -out {}  -applyxfm -init {}".format(volume,FA,out_vol,T12FA), stdout, container)
        run("fslmaths {} -thr 0.2 -bin {} ".format(out_vol,out_vol), stdout, container)

    for volume in glob(join(subcort_vol_dir,"*.nii.gz")):
        out_vol = join(subcort_vol_dir_out,splitext(splitext(split(volume)[1])[0])[0] + "_s2fa.nii.gz")
        write(stdout, "Processing {} -> {}".format(split(volume)[1], split(out_vol)[1]))
        run("flirt -in {} -ref {} -out {}  -applyxfm -init {}".format(volume,FA,out_vol,T12FA), stdout, container)
        run("fslmaths {} -thr 0.2 -bin {}".format(out_vol,out_vol), stdout, container)

    run("fslmaths {} -mul 0 {}".format(FA,bs), stdout, container)  # For now we fake a bs.nii.gz file
    maskseeds(sdir,join(cort_vol_dir + "_s2fa"),join(cort_vol_dir + "_s2fa_m"),0.05,1,1,container)
    maskseeds(sdir,join(subcort_vol_dir + "_s2fa"),join(subcort_vol_dir + "_s2fa_m"),0.05,0.4,0.4,container)
    saveallvoxels(sdir,join(cort_vol_dir + "_s2fa_m"),join(subcort_vol_dir + "_s2fa_m"),allvoxelscortsubcort,container)
    smart_remove(terminationmask)
    run("fslmaths {} -uthr .15 {}".format(FA, terminationmask), stdout, container)
    run("fslmaths {} -add {} {}".format(terminationmask, bs, terminationmask), stdout, container)
    run("fslmaths {} -bin {}".format(terminationmask, terminationmask), stdout, container)
    run("fslmaths {} -mul {} {}".format(terminationmask, allvoxelscortsubcort, intersection), stdout, container)
    run("fslmaths {} -sub {} {}".format(terminationmask, intersection, terminationmask), stdout, container)
    run("fslmaths {} -add {} -add {} {}".format(bs,
                                                join(subcort_vol_dir + "_s2fa_m","lh_thalamus_s2fa.nii.gz"),
                                                join(subcort_vol_dir + "_s2fa_m","rh_thalamus_s2fa.nii.gz"),
                                                exclusion_bsplusthalami), stdout, container)
    for file in glob(join(sdir,"volumes_cortical_s2fa","*.nii.gz")):
        copy(file,EDI_allvols)
    for file in glob(join(sdir,"volumes_subcortical_s2fa","*.nii.gz")):
        copy(file,EDI_allvols)
    write_finish(stdout, "s2b_freesurfer")
    write_checkpoint(sdir, "s2b", checksum)

def create_job(sdir, num_cores, use_gpu, stdout, container, checksum, force):
    s2b_1_future = s2b_1_recon_all(sdir, use_gpu, num_cores, stdout, container, checksum, force)
    return s2b_2_process_vols(sdir, stdout, container, checksum, inputs=[s2b_1_future])
