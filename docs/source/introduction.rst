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
.. figure:: /images/experimental-geometry.png
   :align: right
   :width: 90%
   :figwidth: 40%

   *Experimental geometry used in NXRefine.* 

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

The Φ-axis is approximately perpendicular to the beam. The Φ-axis motor
is on a χ-circle (not shown), with χ = 0° corresponding to a vertical
axis of rotation. The figure shows a configuration, in which χ = -90°.
The orientation of the Φ-axis can also be adjusted in the horizontal
plane by ω and in the vertical plane by θ.

.. note:: This geometry is equivalent to the four-circle geometry
          defined by H. You [see Fig. 1 in J. Appl. Cryst. **32**, 614
          (1999)], with θ and ω corresponding to η and μ, respectively.
          At present, NXRefine assumes that the two angles coupled to
          the detector, δ and ν, are fixed to 0°, with detector
          misalignments handled by the yaw and pitch angles refined in
          powder calibrations.

.. warning:: In earlier versions of NXRefine, θ was called the
             goniometer pitch angle, since it corresponds to a tilting
             of the χ-circle about the horizontal axis. It is still
             referred to as 'gonpitch' in CCTW, the C++ program called
             by NXRefine to transform the detector coordinates to
             reciprocal space.

NXRefine uses the following conventions to define a set of Cartesian
coordinates as laboratory coordinates when all angles are set to 0.

* +X: parallel to the incident beam.
* +Z: parallel to the (usually vertical) axis connecting the base of the
  χ-circle to the sample.
* +Y: defined to produce a right-handed set of coordinates.

In addition to defining the sample orientation, it is necessary to
relate the pixel coordinates of the detector to the instrument
coordinates. Assuming the pixels form a rectangular two-dimensional
array, the detector X-axis corresponds to the fastest-changing
direction, which is normally horizontal, so the orthogonal Y-axis is
usually vertical. The two coordinate systems are then related by:

    | +X(det) = -Y(lab), +Y(det) = +Z(lab), and +Z(det) = -X(lab)

This is defined by an orientation matrix, which can in principle be
changed, although it is currently fixed.