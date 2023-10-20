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
`CCTW <https://sourceforge.net/projects/cctw/>`_` (Crystal Coordination 
Transformation Workflow) is a C++ package written by Guy Jennings. It
is launched as a separate process by NXRefine, which uses the 
experimental metadata to define the settings file used to define the 
input and output grids. It has to be separately installed.

User Support
------------
If you are interested in using this package, please contact Ray Osborn 
(ROsborn@anl.gov). Please report any bugs as a 
[Github issue](https://github.com/axmas/nxrefine/issues), with relevant 
tracebacks.
