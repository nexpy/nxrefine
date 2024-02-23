Installation
============
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
------------------
The following packages are listed as dependencies.

=================  =================================================
Library            URL
=================  =================================================
NeXpy              https://github.com/nexpy/nexpy/
cctbx-base         https://cci.lbl.gov/cctbx_docs/
pyfai              https://pyfai.readthedocs.io/
sqlalchemy         https://docs.sqlalchemy.org/
psutil             https://psutil.readthedocs.io/
persist-queue      https://github.com/peter-wangxu/persist-queue
=================  =================================================

NeXpy
-----
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
----
`CCTW <https://sourceforge.net/projects/cctw/>`_ (Crystal Coordination 
Transformation Workflow) is a C++ package written by Guy Jennings. It
is launched as a separate process by *NXRefine*, which uses the 
experimental metadata to define the settings file used to define the 
input and output grids. It has to be separately installed.

User Support
------------
If you are interested in using this package, please contact Ray Osborn 
(ROsborn@anl.gov). Please report any bugs as a 
`Github issue <https://github.com/nxrefine/nxrefine/issues>`_, with
relevant tracebacks.

