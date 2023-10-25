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

**nxserver.log**

  This is a log file that records jobs submitted to the server queue.

**cpu1.log**, **cpu2.log**, ...
  
  These are log files that contain the output of jobs running on the
  server. The number depends on the number of simultaneous jobs that
  are allowed on the server, which is defined by the settings file.

**settings.ini**
  
  A file containing default settings used by the NXRefine package,
  including server parameters, instrumental parameters, and parameters
  used in the data reduction workflow. When a new experiment is set up,
  a copy of these parameters is stored in the experiment directory (to
  be described later), so that they can be customized if necessary.
  These settings are described below.

**nxsetup.sh**
  
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

**nxcommand.sh**
  
  A shell script that is used if jobs need to be wrapped before
  submission to the job queue, *e.g.*, using ``qsub``. Here is an
  example, in which ``nxsetup.sh`` is run in order to initialize
  NXRefine.::

    echo `date` "USER ${USER} JOB_ID ${JOB_ID}"
    source /path/to/parent/nxserver/nxsetup.sh
    <NXSERVER>

**task_list**
  
  A directory that contains files that implement a file-based FIFO
  queuing system for server jobs.

**locks**
  
  A directory that contains files that implement the
  `nexusformat <https://nexpy.github.io/nexpy/>`_ file-locking system.
  Locked files can be viewed, and removed if they are stale, using the
  ``Show File Locks`` dialog in the NeXpy ``File`` menu. 

.. note:: The log files can be viewed using the ``Manage Server`` dialog
          and the settings file can be modified using the ``Edit
          Settings`` dialog, both of which are located in the ``Server``
          menu added as a NeXpy plugin when NXRefine is installed.

Default Settings
^^^^^^^^^^^^^^^^
The file, ``settings.ini`` in the server directory contains the default
settings for the server, the beamline, and the workflow. These values
can be changed, either by opening the "Edit Settings" dialog in the
NeXpy "Server" menu or at the command line using ``nxsettings -i``.
Hitting the [Return] key keeps the current value. 

.. figure:: /images/server_settings.png
   :align: right
   :width: 90%
   :figwidth: 30%

The right-hand figure shows an example of the first two sections of the
``settings.ini``. The other sections contain default values of the data
reduction parameters that can be customized for each experiment (see the
next section).

**Server Settings**
The server settings are used by the workflow server, which is described
in a later section.

:type: The server type can either be ``multicore`` or ``multinode``. The
       only difference is that multinode servers have a list of defined
       nodes, to which jobs may be submitted, so their names will also
       be stored in the settings file. If jobs are submitted to a job
       server, without needing to specify the node, or if all the jobs
       are performed on the local machine, then the server type should
       be ``multicore``.

:cores: This sets the number of jobs that can be run simultaneously by
        the server. Once reaching the limit, new jobs will only start as
        old ones are finished.

:concurrent: This determines whether parallelized processes should be
             used in the workflow. These speed up the computation, but
             can be disabled if they cause issues with the server. Note
             that this refers to whether multiple processes can be run
             simultaneously, *e.g.*, in peaks searches, not whether
             multiple jobs can be submitted to the server. Valid values
             are ``True`` or ``False``.

:run_command: This is a string that is prepended to any jobs that are
              submitted to the server. It can contain a set of switches
              in addition to the job submission command itself.

:template: In some systems, it is necessary to wrap the command that is
           submitted to the server in a shell script. This is the name
           of the script, which should be stored in the ``nxserver``
           directory. It should contain the string ``<NXSERVER>``,
           which is replaced by the job command.

:cctw: This is the path to the CCTW executable used to transform data
       from instrumental coordinates to reciprocal space.

**Instrument Settings**
The instrument settings are used to define the name of the instrument,
which is used to import a customized plugin for importing metadata,
and a set of paths defining the location of the raw and reduced data
locations.
