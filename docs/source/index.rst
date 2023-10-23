.. NXRefine documentation master file, created by
   sphinx-quickstart on Wed Oct 11 14:36:33 2023.

NXRefine
========
Recent advances in synchrotron x-ray instrumentation have enabled the
rapid acquisition of x-ray diffraction data from single crystals,
allowing large contiguous volumes of scattering in reciprocal space to
be collected in a matter of minutes. Typically, the sample is rotated
continuously in a monochromatic beam while images are collected on a
fast area detector. These images are stacked into three-dimensional
arrays and transformed from detector coordinates to reciprocal space
coordinates, using an orientation matrix derived from the measured
Bragg peaks.

NXRefine implements a complete workflow for both data acquisition and 
reduction of single crystal x-ray scattering. Advanced workflows exist
for the generation of Bragg peak intensities used by crystallographers
to solve the average crystalline structure. However, the goal of
NXRefine is to generate a three-dimensional mesh of scattering intensity
that includes both Bragg peaks and the diffuse scattering that arises
from deviations from the average structure. 

The workflow is written as a set of Python modules that can either be
run from the command line, launched from a GUI that is implemented as a
plugin to `NeXpy <https://nexpy.github.io.nexpy/>`_, or by submitting
jobs to a batch queue. After the initial refinement of the sample
orientation, the entire workflow can be run in an automated fashion,
while the data is being collected so that reduced data is available for
inspection before a set of measurements, *e.g.*, as a function of
temperature, are complete.

.. toctree::
   :maxdepth: 2

   introduction
   installation
   experiment

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
