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

This will create a directory at ``/path/to/parent/nxserver`` containing
the files that are required by NXRefine server.

.. note:: If the supplied path already ends in ``nxserver``, it will not
          be appended.

All the files in the ``nxserver`` directory will have group read/write
permissions to allow them to be updated by multiple users in that group.

This also adds a hidden file to the home directory, containing the path
to the server directory, so that the server path can be read in future
login sessions. Each user should then issue the same command to store
the server directory in their own home directory. If the server
directory already exists, it is not touched. In principle, this only
needs to be run once, but it could be 

NXRefine uses file-based locking to prevent corruption of data files.
This system is provided by the 
`nexusformat package <https://nexpy.github.io/nexpy/>`_, which defines
the directory to contain the lock files using the ``NX_LOCKDIRECTORY``
environment variable. It is recommended that this directory be placed
within the server directory.

.. note:: The NeXpy GUI has a settings file that can be used to define
          the lock directory, but it is overridden by the environment
          variable if it is defined. This allows system administrators
          to set up a unique lock file directory for all their users.

Server Directory
^^^^^^^^^^^^^^^^
Here is the structure of the ``nxserver`` directory::

    nxserver
    ├── nxserver.log
    ├── cpu1.log
    ├── cpu2.log
    ├── cpu3.log
    ├── settings.ini
    ├── nxcommand.sh
    └── task_list
        ├── info
        └── q00000
    └── locks
        ├── ...
        └── ...

* **nxserver.log**

  This is a log file that records jobs submitted to the server queue.

* **cpu1.log**, **cpu2.log**, ...
  
  These are log files that contain the output of jobs running on the
  server. The number depends on the number of simultaneous jobs that
  are allowed on the server, which is defined by the settings file.

* **settings.ini**
  
  A file containing default settings used by the NXRefine package,
  including server parameters, instrumental parameters, and parameters
  used in the data reduction workflow. When a new experiment is set up,
  a copy of these parameters is stored in the experiment directory (to
  be described later), so that they can be customized if necessary.
  These settings are described below.

* **nxsetup.sh**
  
  A shell script that could be used to initialize paths to the server
  directory or environment variables used by NeXpy. This could be run
  within a user's ``~/.bashrc`` file, or by other shell scripts used to
  launch NXRefine workflow jobs (see below). Here is an example of what
  this file could contain.::

    export NX_LOCKDIRECTORY=/path/to/parent/nxserver/locks
    export NX_LOCK=10
    nxserver -d /path/to/parent/nxserver

  Other commands, *e.g.*, to initialize a particular conda environment,
  could be also be added to this file.

* **nxcommand.sh**
  
  A shell script that is used if jobs need to be wrapped before
  submission to the job queue, *e.g.*, using ``qsub``. Here is an
  example, in which ``nxsetup.sh`` is run in order to initialize
  NXRefine.::

    echo `date` "USER ${USER} JOB_ID ${JOB_ID}"
    source /path/to/parent/nxserver/nxsetup.sh
    <NXSERVER>

* **task_list**
  
  A directory that contains files that implement a file-based FIFO
  queuing system for server jobs.

* **locks**
  
  A directory that contains files that implement the
  `nexusformat <https://nexpy.github.io/nexpy/>`_ file-locking system.
  Locked files can be viewed, and removed if they are stale, using the
  ``Show File Locks`` dialog in the NeXpy ``File`` menu. 

.. note:: The log files can be viewed using the ``Manage Server`` dialog
          and the settings file can be modified using the ``Edit
          Settings`` dialog, both of which are located in the ``Server``
          menu added as a NeXpy plugin when NXRefine is installed.

Server Settings
---------------
The file, ``settings.ini`` in the server directory contains settings for
the server, the beamline, and the workflow. These values can be changed,
either by opening the "Edit Settings" dialog in the NeXpy "Server" menu
or at the command line using ``nxsettings -i``. Hitting the [Return] key
keeps the current value. Here are the parameters::

    $ nxsettings -i 

    Default settings stored in /path/to/parent/nxserver 


    server Parameters 
    ------------------- 
    type [multicore]:  
    cores [10]:
    concurrent [False]:
    run_command [qsub -q chess.q]:  
    template [/path/to/parent/nxserver/nxcommand.sh]:
    cctw [cctw]:  

    instrument Parameters 
    ------------------- 
    source [CHESS]:
    instrument [QM2]:
    raw_home [/nfs/chess/id4b]:
    raw_path [raw6M]: 
    analysis_home [/nfs/chess/id4baux]: 
    analysis_path [nxrefine]: 
    experiment []: 

    NXRefine Parameters 
    ------------------- 
    wavelength [0.3351]:  
    distance [511.312]:  
    geometry [default]:
    phi [-5]:
    phi_end [360]:
    phi_step [-0.1]:
    chi [0]:
    omega [0]:
    gonpitch [0]:
    x [0]:
    y [0]:
    nsteps [3]:
    frame_rate [10]:

    NXReduce Parameters 
    ------------------- 
    threshold [50000]:
    min_pixels [10]:
    first [10]:
    last [3640]:
    polar_max [10]:
    monitor [monitor1]:
    norm [15000]:
    qmin [4]:
    qmax [11]:
    radius [0.2]:
