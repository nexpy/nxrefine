Data Reduction
**************
In order to reduce raw data collected as images (or frames) on an area
detector as a function of sample rotation angle and transform the
results into reciprocal space maps, *i.e.*, S(**Q**), *NXRefine*
performs the following steps:

* combining the frames into a single three-dimensional array.
* harvesting metadata collected during the sample rotations.
* summing detector frames to facilitate absorption corrections.
* searching for Bragg peaks embedded within the raw data.
* defining an orientation matrix.
* transforming the raw data into reciprocal space coordinates.

When multiple sample rotations are performed to collect a single data
set, these steps have to be applied to each rotation scan and the
results merged to produce a single three-dimensional array representing
S(**Q**). Optionally, *NXRefine* also transforms the data after applying
masks that eliminate spurious signals caused by the scattering of Bragg
peaks within the detector sensor layer.

Once the data has been transformed into S(**Q**), it is possible to
generate 3D-ΔPDF maps, which transform the data back into real space,
producing difference Patterson maps, *i.e.*, maps of interatomic vector
probabilities, which differ from the average crystalline structure. In
this way, continuous distributions of diffuse scattering intensity are
typically reduced to discrete peaks, with positive and negative
intensities, representing these probability differences. *NXRefine*
implements the "punch-and-fill" method, described by `Weber and Simonov
<https:dx.doi.org.10.1524/zkri.2012.1504>`_.

Nearly all of the steps in the *NXRefine* data reduction workflow can
either be performed from the command line or launched from a NeXpy GUI.
The exception is determining the crystal orientation, which must first
be performed using the `Refine Lattice` dialog in NeXpy. Once the sample
orientation has been determined from one of the measurements, *e.g.*, at
room temperature, it can be copied and refined automatically when
reducing the data from other measurements, provided the space group has
not changed or is still compatible with the observed Bragg peaks. 


