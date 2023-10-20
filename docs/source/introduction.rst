Introduction
============
NXRefine implements a complete workflow for both data acquisition and 
reduction of single crystal x-ray scattering, collected by the sample
rotation method. NXRefine generates a three-dimensional mesh of
scattering intensity, *i.e.*, S(Q), which can be used either to model
diffuse scattering in reciprocal space or to transform the data to
produce three-dimensional pair-distribution-functions (PDF), which
represent the summed probabilities of all possible interatomic vectors.
In crystallography, these are known as Patterson maps. If the Bragg
peaks are eliminated before these transforms, using a process known as
'punch-and-fill,' only those probabilities that deviate from the average
crystalline structure are retained, generating 'difference' Patterson,
or 3D-ΔPDF, maps. The final stage of the NXRefine workflow is to
generate such 3D-ΔPDF maps.

The uncompressed raw data from such measurements comprises tens (and
sometimes hundreds) of gigabytes, often collected in under 30 minutes.
This allows such measurements to be repeated multiple times as a
function of a parametric variable, such as temperature. Ideally, such
data should be transformed into reciprocal space as quickly as it is
measured, so that scientists can inspect the results before a set of
scans is complete. For this reason, NXRefine enables the workflow to be
run automatically once an initial refinement of the sample orientation
has been determined.

Experimental Geometry
---------------------
NXRefine is designed for experiments, in which the sample is placed in a
monochromatic x-ray beam and rotated continuously about a Φ-axis that is
approximately perpendicular to the beam. Images are collected on an area
detector placed in transmission geometry behind the sample. Detectors
such as the Dectris Pilatus series consist of a set of chips with small
gaps between them, so sample rotation scans are often repeated three
times with small detector translations between each one. However, it is
also possible to fill in the gaps just by adjusting the orientation of
the Φ-axis itself. NXRefine reduces the data independently for each
rotation scan before merging them to create a single 3D data volume.

.. figure:: /images/experimental-geometry.png
   :align: right
   :width: 40%

   Experimental geometry used in NXRefine. 

The Φ-axis is approximately perpendicular to the beam. The Φ-axis motor
is on a χ-circle (not shown), with χ = 0° corresponding to a vertical
axis of rotation. The figure shows a configuration, in which χ = -90°.
The orientation of the Φ-axis can also be adjusted in the horizontal
plane by ω and in the vertical plane by θ.

.. note:: This geometry is equivalent to the four-circle geometry
          defined by H. You [see Fig. 1 in J. Appl. Cryst. **32**, 614
          (1999)], with θ coreesponding to η and ω corresponding to μ.
          At present, NXRefine assumes that the two angles coupled to
          the detector, δ and ν, are fixed to 0°, with detector
          misalignments handled by the yaw and pitch angles refined in
          powder calibrations.
