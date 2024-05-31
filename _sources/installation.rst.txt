Installation
************
Currently, *NXRefine* must be installed from source by cloning the 
`NXRefine Git repository <https://github.com/nexpy/nxrefine>`_::

    $ git clone https://github.com/nexpy/nxrefine.git

Then use standard Python tools to build and/or install a distribution
from within the source directory::

    $ python -m build  # build a distribution
    $ python -m pip install .  # install the package

In the near future, *NXRefine* will be uploaded to the PyPI server so
that it can be installed without downloading the source code.

Required Libraries
==================
The following packages are listed as dependencies.

=================  =================================================
Library            URL
=================  =================================================
NeXpy              https://github.com/nexpy/nexpy/
nexusformat        https://github.com/nexpy/nexusformat/
cctbx-base         https://cci.lbl.gov/cctbx_docs/
pyfai              https://pyfai.readthedocs.io/
sqlalchemy         https://docs.sqlalchemy.org/
psutil             https://psutil.readthedocs.io/
persist-queue      https://github.com/peter-wangxu/persist-queue
=================  =================================================

NeXpy
=====
Although much of the *NXRefine* workflow can be performed using
command-line scripts, it is recommended that they are used in
conjunction with the Python-based GUI, `NeXpy
<https://nexpy.github.io/nexpy>`_. Once NXRefine has been installed,
*NeXpy* will automatically import a set of plugins that add three menu
items to the *NeXpy* menu bar.

.. figure:: /images/NeXpy-GUI.png
   :align: center
   :width: 90%
   :figwidth: 100%

* **Experiment**
  
  Dialogs to set up experiment directories, initialize NeXus templates,
  perform powder calibrations, create NeXus files for linking to the
  scans and storing data reduction results, and, if necessary, import
  existing scan data.

* **Refine**
  
  Dialogs to define data reduction parameters, perform peak searches,
  refine crystal orientations, and prepare the reciprocal space grids
  for the transformed data.

* **Server**
  
  Dialogs to manage workflow operations on existing data, view server
  logs, and edit default settings for future experiments.

.. note:: If the *NXRefine* menu items do not appear in the menu bar, 
          check the NeXpy log file ("Show Log File" in the Window menu) 
          for any error messages preventing the plugin from being
          loaded.

The menus will be described in more detail in subsequent sections.

CCTW
====
`CCTW <https://sourceforge.net/projects/cctw/>`_ (Crystal Coordination 
Transformation Workflow) is a C++ package written by Guy Jennings. It
is launched as a separate process by *NXRefine*, which uses the 
experimental metadata to define the settings file used to define the 
input and output grids. It has to be separately installed.

Initial Setup
=============
In order to allow *NXRefine* to be used by multiple users on a single
machine or cluster, a common directory is defined to store log files,
task queues, and default settings. The location of this directory should
be defined immediately after installing *NXRefine* for the first time.
Since the files in this directory are modified by *NXRefine* commands
that could be run by multiple users, it is recommended that all such
users are members of the same group. When initialized by a member of
that group, the files in the server directory have group read/write
permissions by default.

The location of the server directory is initialized on the command line
by the 'nxserver' command::

    $ nxserver -d /path/to/parent

This will create a directory at ``/path/to/parent/nxserver`` containing
the files that are required by *NXRefine* server. 

.. note:: If the supplied path already ends in ``nxserver``, it will not
          be appended.

Once the server directory has been initialized, it is necessary for its
location to be defined for other users. This can be done in one of two
ways. 

1. If *NXRefine* is being configured by a system administrator, it is
   possible to use a system-wide environment variable, ``NX_SERVER``, to
   to define the path to the server directory. Alternatively, this
   environment variable could be added to each user's login script.

2. The ``nxserver`` command used to initialize the server directory also
   adds a hidden file to the user's home directory,
   ``~/.nxserver/settings.ini``, which contains the server directory
   path. If the server directory already exists, the command can be run
   again by other users without affecting the initial directory. In
   principle, it only needs to be run once by each user, although it
   could also be added to a login script if preferred.

   .. note:: If the ``NX_SERVER`` environment variable is defined, it 
             takes precedence over the path in
             ``~/.nxserver/settings.ini``.

*NXRefine* uses file-based locking to prevent corruption of data files.
This system is provided by the 
`nexusformat package <https://nexpy.github.io/nexpy/>`_, which defines
the directory to contain the lock files using the ``NX_LOCKDIRECTORY``
environment variable. It is recommended that this directory be placed
within the server directory.

.. note:: The *NeXpy* GUI has a settings file that can be used to define
          the lock directory, but it is overridden by the environment
          variable if it is defined. This allows system administrators
          to set up a unique lock file directory for all their users.

User Support
------------
If you are interested in using this package, please contact Ray Osborn 
(ROsborn@anl.gov). Please report any bugs as a 
`Github issue <https://github.com/nxrefine/nxrefine/issues>`_, with
relevant tracebacks.
