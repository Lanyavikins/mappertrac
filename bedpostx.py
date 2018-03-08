from sys import argv
ffrom sys import argv
from os.path import exists,join,split,splitext,abspath
from os import system,mkdir,remove,environ
from shutil import *

def smart_copy(src,dest,force=False):
    if force or not exists(dest):
        copyfile(src,dest)
 
if len(argv) < 4:
    print "Usage: %s <target-dir> <subject-id> [force]" % argv[0]
    exit(0)

# Check whether the right environment variables are set
FSL_DIR = join(environ["FSL_DIR"],"bin")
if not exists(FSL_DIR):
    print "Cannot find FSL_DIR environment variable"
    exist(0)


# Shall we force a re-computation
force = ((len(argv) > 3) and argv[3] == 'force')



# root directory
root = join(abspath(argv[1]),argv[2])

if not exists(join(root,"bedpostx_b1000")):
    mkdir(join(root,"bedpostx_b1000"))

bedpostx = join(root,"bedpostx_b1000")

smart_copy(join(root,"data_eddy.nii.gz"),join(bedpostx,"data.nii.gz"),force)
smart_copy(join(root,"data_bet_mask.nii.gz"),join(bedpostx,"nodif_brain_mask.nii.gz"),force))
smart_copy(join(root,"bvals"),join(bedpostx,"bvals"),force))
smart_copy(join(root,"bvecs"),join(bedpostx,"bvecs"),force))

              


#system("time " + join(FSL_DIR,"bedpostx") +  " " + bedpostx)

