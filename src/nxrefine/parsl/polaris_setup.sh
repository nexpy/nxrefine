# Environment setup for NXRefine tasks on Polaris at the ALCF.
#
# Copy this file into the server directory, the one holding settings.ini,
# edit the paths below, and name it in the [parsl] section:
#
#     worker_init = polaris_setup.sh
#
# It is sourced by each batch job before the Parsl workers are started,
# so it needs neither a shebang nor execute permission. Every command
# has to be safe to run in a non-interactive shell, and anything the
# tasks need has to be exported.

# Compute nodes start with a bare environment, so the modules providing
# conda have to be loaded again here.
module use /soft/modulefiles
module load conda

# Activate the environment holding nxrefine and its dependencies. Give
# the full path rather than the environment name, so that the job does
# not depend on the conda configuration in the home directory.
conda activate /path/to/nxrefine-env

# NXRefine finds the server settings and the lock directory through
# these, and neither is inherited from the login node.
export NX_SERVER=/path/to/analysis/nxserver
export NX_LOCKDIRECTORY=/path/to/analysis/nxserver/locks

# Uncomment if cctw, used by the transform tasks, is not on the path of
# the activated environment. The executable itself is named by the
# 'cctw' setting in the [server] section.
# export PATH=/path/to/cctw/bin:$PATH
