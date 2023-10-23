Installation
============
Currently, NXRefine must be installed from source by cloning the 
`NXRefine Git repository <https://github.com/nexpy/nxrefine>`_::

    $ git clone https://github.com/nexpy/nxrefine.git

Then use standard Python tools to build and/or install a distribution
from within the source directory::

    $ python -m build  # build a distribution
    $ python -m pip install .  # install the package

In the near future, NXRefine will be uploaded to the PyPI server so that
it can be installed without downloading the source code.

Required Libraries
------------------
The following packages are listed as dependencies.

=================  =================================================
Library            URL
=================  =================================================
NeXpy              https://github.com/nexpy/nexpy/
cctbx-base         https://cci.lbl.gov/cctbx_docs/
pyfai              https://pyfai.readthedocs.io/
sqlalchemy         https://docs.sqlalchemy.org/
psutil             https://psutil.readthedocs.io/.io/
=================  =================================================

CCTW
----
`CCTW <https://sourceforge.net/projects/cctw/>`_ (Crystal Coordination 
Transformation Workflow) is a C++ package written by Guy Jennings. It
is launched as a separate process by NXRefine, which uses the 
experimental metadata to define the settings file used to define the 
input and output grids. It has to be separately installed.

User Support
------------
If you are interested in using this package, please contact Ray Osborn 
(ROsborn@anl.gov). Please report any bugs as a 
`Github issue <https://github.com/nxrefine/nxrefine/issues>`_, with
relevant tracebacks.

Initial Setup
-------------
In order to allow NXRefine to be used on machines with multiple users,
a directory is defined to store log files, task queues, and settings.
This directory can be initialized on the command line by the 'nxserver'
command:

    $ nxserver -d /path/to/parent

This will create a directory at '/path/to/parent/nxserver' containing
the files that are required by NXRefine server.

.. note:: If the supplied path already ends in 'nxserver,' it will not
          be appended.

All the files in the 'nxserver' directory will have group read/write
permissions to allow them to be updated by multiple users in that group.

This also adds a hidden file to the home directory pointing to the
server directory, so that the server path can be read in future login
sessions. Each user should then issue the same command to store the
server directory in their own home directory. If the server directory
already exists, it is not touched. In principle, this only needs to be
run once, 

NXRefine uses file-based locking to prevent corruption of data files.
This system is provided by the 
`nexusformat package <https://nexpy.github.io/nexpy/>`_, which defines
the directory to contain the lock files using the NX_LOCKDIRECTORY
environment variable. It is recommended that this directory be placed
within the server directory.

.. note:: The NeXpy GUI has a settings file that can be used to define
          the lock directory, but it is overridden by the environment
          variable if it is defined. This allows system administrators
          to set up a unique lock file directory for all their users.

It is suggested that users add the following to their .bashrc file::

    export NX_LOCKDIRECTORY=/nfs/chess/id4baux/nxserver/locks
    export NX_LOCK=10
    nxserver -d /nfs/chess/id4baux/nxserver

