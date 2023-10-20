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

.. image:: /images/experimental-geometry.png
   :align: center
   :width: 90%

