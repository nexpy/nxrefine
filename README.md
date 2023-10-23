Introduction
============
NXRefine implements a complete workflow for both data acquisition and 
reduction of single crystal diffuse x-ray scattering collected as a 
series of area detector frames during continuous sample rotation. The
data are stored in HDF5 files, which conform to the NeXus data format
standard. These files contain a comprehensive set of metadata, including
the incident wavelength, powder calibration scans used to define 
detector distances, beam centers, and yaw, pitch, and roll corrections. 
Automated peak searches of the three-dimensional data arrays define 
a set of Bragg peaks that are used to define an orientation matrix, 
defined according to Busing and Levy, which is then used to transform
the data from angular coordinates to reciprocal space coordinates using
the CCTW program. Multiple rotations at different detector translations
and offset rotation axes are combined to ensure that there are no gaps 
in the reconstructed data, and allow the construction of masks to 
eliminate detector artifacts due to Compton scattering within the 
sensor layers. Finally, the data can be transformed into 3D-ΔPDF maps
using the punch-and-fill method after symmetrization. 

The workflow is implemented as plugins to the 
[NeXpy package](http://nexpy.github.io/nexpy) that are used to set up 
the basic experimental configuration and sample parameters, and 
determine the orientation matrix. The remaining components of the 
workflow can be run as command-line scripts, or submitted to a queue
for distribution to multiple nodes or processes for simultaneous 
reduction of multiple datasets.

Instructions for running NXRefine are under development. 

The NXRefine package is being developed as part of a DOE-funded project
to utilize advanced computational methods for the analysis of 
single-crystal x-ray scattering from synchrotron sources, such as 
multidimensional spectral analysis and machine learning. Further details
of this project are available on the 
[AXMAS web pages](https://cels.anl.gov/axmas).

Installing and Running
======================
The source code can be downloaded from the AXMAS Git repository:

```
    $ git clone https://github.com/nexpy/nxrefine.git
```

To install in the standard Python location:

```
    $ pip install .
```
Prerequisites
=============
Python Packages
---------------
The following packages are listed as dependencies.

* [nexpy](https://github.com/nexpy/nexpy/)
* [cctbx-base](https://cci.lbl.gov/cctbx_docs/)
* [pyfai](https://pyfai.readthedocs.io/)
* [sqlalchemy](https://docs.sqlalchemy.org/)
* [psutil](https://psutil.readthedocs.io/)

CCTW
----
[CCTW](https://sourceforge.net/projects/cctw/) (Crystal Coordination 
Transformation Workflow) is a C++ package written by Guy Jennings. It
is launched as a separate process by NXRefine, which uses the 
experimental metadata to define the settings file used to define the 
input and output grids. It has to be separately installed.

User Support
============
If you are interested in using this package, please contact Ray Osborn 
(ROsborn@anl.gov). Please report any bugs as a 
[Github issue](https://github.com/nexpy/nxrefine/issues), with relevant 
tracebacks.
