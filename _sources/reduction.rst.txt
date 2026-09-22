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

.. note::

   The following scripts share four common command-line switches that
   are not described individually under each command:

   ``-d / --directory DIRECTORY``
       The scan directory containing the NeXus wrapper file and raw
       data. Required by all per-scan scripts.

   ``-e / --entries ENTRIES …``
       Restrict processing to the named NeXus entries (e.g.,
       ``f1 f2 f3``). If omitted, all entries in the wrapper file are
       processed.

   ``-o / --overwrite``
       Force the step to re-run even if a result from a previous run is
       already stored in the file.

   ``-q / --queue``
       Instead of running immediately, add the task to the server queue
       (see :ref:`nxserver`).

nxload
------
On beamlines that require it, ``nxload`` actively retrieves or converts
raw detector data from the beamline storage system. On others it simply
confirms that the expected raw HDF5 files are present on disk before
the rest of the workflow proceeds. There are no scan-specific parameters
beyond the common switches.

.. code-block::

    usage: nxload [-h] -d DIRECTORY [-e ENTRIES [ENTRIES ...]] [-o] [-q]

    Load raw data

    options:
      -h, --help            show this help message and exit
      -d, --directory DIRECTORY
                            scan directory
      -e, --entries ENTRIES [ENTRIES ...]
                            names of entries to be loaded
      -o, --overwrite       overwrite existing peaks
      -q, --queue           add to server task queue

nxlink
------
``nxlink`` populates the NeXus wrapper file with metadata from the
beamline. It creates the ``data`` group that links to the raw pixel
array stored in the HDF5 file and defines the frame-number, x-pixel,
and y-pixel coordinate axes. It also imports the scan logs recorded
during the rotation — motor positions, temperatures, and timing
records — together with the monitor counts that will later be used for
intensity normalization. There are no scan-specific parameters beyond
the common switches.

.. code-block::

    usage: nxlink [-h] -d DIRECTORY [-e ENTRIES [ENTRIES ...]] [-o] [-q]

    Link data and metadata to NeXus file

    options:
      -h, --help            show this help message and exit
      -d, --directory DIRECTORY
                            scan directory
      -e, --entries ENTRIES [ENTRIES ...]
                            names of entries to be searched
      -o, --overwrite       overwrite existing peaks
      -q, --queue           add to server task queue

nxmax
-----
``nxmax`` scans every frame in the detector stack to compute several
frame-level quantities needed for normalization and sample-transmission
corrections:

* The maximum pixel count over the entire dataset, which sets the scale
  for subsequent thresholds.
* An integrated detector image summed over all frames
  (``frame_sums/summed_data``), useful for identifying hot pixels and
  for absorption-correction diagnostics.
* A per-frame intensity baseline (``frame_sums/summed_frames``) derived
  from a trimmed sum over an annular ring of pixels on the detector.
  The ring is chosen to lie away from Bragg reflections; the brightest
  10 % of pixels within it are discarded before summing so that
  residual Bragg contamination does not bias the result.
* A sample-transmission curve as a function of frame number
  (``frame_sums/transmission``), obtained by normalizing the per-frame
  baseline by the monitor counts and then applying a 31-frame median
  filter to remove transient spikes.
* A radial sum (``frame_sums/radial_sum``) as a function of 2θ,
  computed by pyFAI if calibration data are available in the wrapper
  file.

The ``-f / --first`` and ``-l / --last`` options restrict the range of
frames that are processed (frames outside this range are excluded from
all sums and from the peak search in ``nxfind``).

The ``--qmin`` and ``--qmax`` options set the inner and outer
boundaries (in Å⁻¹) of the annular transmission window. If omitted,
values are derived automatically from the detector geometry.

.. code-block::

    usage: nxmax [-h] -d DIRECTORY [-e ENTRIES [ENTRIES ...]]
                 [-s SUBENTRY] [-f FIRST] [-l LAST] [--qmin QMIN] [--qmax QMAX]
                 [-o] [-q]

    Find maximum counts of the signal in the specified path

    options:
      -h, --help            show this help message and exit
      -d, --directory DIRECTORY
                            scan directory
      -e, --entries ENTRIES [ENTRIES ...]
                            names of entries to be processed
      -s, --subentry SUBENTRY
                            subentry to be processed
      -f, --first FIRST     first frame
      -l, --last LAST       last frame
      --qmin QMIN           minimum scattering Q (Å⁻¹); auto if omitted
      --qmax QMAX           maximum scattering Q (Å⁻¹); auto if omitted
      -o, --overwrite       overwrite existing maximum
      -q, --queue           add to server task queue

nxfind
------
``nxfind`` searches the three-dimensional detector/frame data array for
Bragg peaks. The data is read in overlapping 50-frame chunks and a
blob-detection algorithm locates connected groups of pixels whose
intensity exceeds the threshold and which are separated from other
peaks by more than a minimum pixel distance. The resulting peak list
records, for each reflection, the centroid position in detector
coordinates (x, y) and frame number (z), the integrated intensity, the
widths in each dimension (σ_x, σ_y, σ_z), and the polar and azimuthal
angles computed from the refined detector geometry.

The ``-t / --threshold`` option sets the minimum intensity (in counts)
a pixel must reach to be considered part of a peak. The
``-f / --first`` and ``-l / --last`` options restrict the frame range
searched. The ``-P / --pixels`` option sets the minimum number of
pixels by which two peaks must be separated; peaks that are closer than
this distance are merged.

.. code-block::

    usage: nxfind [-h] -d DIRECTORY [-e ENTRIES [ENTRIES ...]]
                  [-t THRESHOLD] [-f FIRST] [-l LAST] [-P PIXELS]
                  [-s SUBENTRY] [-o] [-p PARENT] [-q]

    Find peaks within the NeXus data

    options:
      -h, --help            show this help message and exit
      -d, --directory DIRECTORY
                            scan directory
      -e, --entries ENTRIES [ENTRIES ...]
                            names of entries to be searched
      -t, --threshold THRESHOLD
                            peak threshold
      -f, --first FIRST     first frame
      -l, --last LAST       last frame
      -P, --pixels PIXELS   minimum pixels between peaks
      -s, --subentry SUBENTRY
                            subentry to be processed
      -o, --overwrite       overwrite existing peaks
      -p, --parent PARENT   The parent .nxs file to use
      -q, --queue           add to server task queue

nxrefine
--------
``nxrefine`` determines the crystal orientation matrix by matching the
Bragg peaks found by ``nxfind`` to the HKL positions predicted by the
known unit cell. If a parent file is configured, the orientation matrix
it contains is used as the starting point; otherwise the initial matrix
must have been set manually using the *Refine Lattice* dialog in NeXpy.
The refinement proceeds in two stages: first, HKL indices are assigned
to observed peaks that fall within the Q-tolerance, and the goniometer
misset angles (chi, omega, theta) are optimized; second, the full 3×3
orientation matrix is refined. For the first entry in a scan set,
``--lattice`` additionally allows the unit-cell parameters (a, b, c, α,
β, γ) to be refined simultaneously; for subsequent entries the lattice
parameters from the first entry are used without modification.

The ``-l / --lattice`` flag enables unit-cell refinement (in addition
to the orientation matrix). The ``-p / --polar_max`` option limits the
refinement to reflections within a given polar angle (in degrees),
which is useful for excluding high-angle peaks that are less
well-measured. The ``-T / --hkl_tolerance`` option sets the Q-distance
(in Å⁻¹) within which an observed peak must lie from its predicted HKL
position in order to be included in the fit.

.. code-block::

    usage: nxrefine [-h] -d DIRECTORY [-e ENTRIES [ENTRIES ...]] [-l]
                    [-p POLAR_MAX] [-T HKL_TOLERANCE] [-s SUBENTRY] [-o] [-q]

    Refine lattice parameters and goniometer angles

    options:
      -h, --help            show this help message and exit
      -d, --directory DIRECTORY
                            scan directory
      -e, --entries ENTRIES [ENTRIES ...]
                            names of entries to be processed
      -l, --lattice         refine lattice parameters
      -p, --polar_max POLAR_MAX
                            maximum polar angle in degrees
      -T, --hkl_tolerance HKL_TOLERANCE
                            tolerance for including peak in Å-1
      -s, --subentry SUBENTRY
                            subentry to be processed
      -o, --overwrite       overwrite existing maximum
      -q, --queue           add to server task queue

nxprepare
---------
``nxprepare`` constructs a three-dimensional boolean mask in
detector/frame space that identifies every voxel occupied by a Bragg
reflection. When ``nxtransform`` is later run with the ``--mask`` flag,
the marked voxels are excluded from the reciprocal-space transform,
suppressing Bragg-peak contributions in the diffuse-scattering signal.

The mask is produced by two successive convolution passes over the raw
data:

* A **fine** pass, with threshold ``--t1`` and convolution half-size
  ``--h1`` pixels, captures the bright core of each Bragg reflection.
* A **coarse** pass, with threshold ``--t2`` and convolution half-size
  ``--h2`` pixels, captures the weaker tails and diffraction streaks
  that spread out around strong reflections.

The combined mask is stored in a separate file (``<entry>_mask.nxs``)
and linked into the wrapper. Default values (t1 = 2.0, h1 = 11,
t2 = 0.8, h2 = 51) work well for many datasets; they can be adjusted
if peaks are being over- or under-masked.

.. code-block::

    usage: nxprepare [-h] -d DIRECTORY [-e ENTRIES [ENTRIES ...]]
                     [--t1 T1] [--h1 H1] [--t2 T2] [--h2 H2]
                     [-s SUBENTRY] [-o] [-q]

    Prepare 3D mask around Bragg peaks

    options:
      -h, --help            show this help message and exit
      -d, --directory DIRECTORY
                            scan directory
      -e, --entries ENTRIES [ENTRIES ...]
                            names of entries to be processed
      --t1 T1               threshold for smaller convolution
      --h1 H1               size of smaller convolution
      --t2 T2               threshold for larger convolution
      --h2 H2               size of larger convolution
      -s, --subentry SUBENTRY
                            subentry to be processed
      -o, --overwrite       overwrite existing mask
      -q, --queue           add to server task queue

nxtransform
-----------
``nxtransform`` transforms the raw detector/frame data into a regular
grid in reciprocal space (H, K, L) using CCTW (Crystallographic
Coordinate Transformation Workflow). Each detector frame is mapped onto
the reciprocal-space grid according to the crystal orientation at the
corresponding rotation angle, as determined by ``nxrefine``.
Intensities are normalized by dividing by the per-frame monitor counts
and by the sample-transmission correction derived by ``nxmax``.

The reciprocal-space grid is defined with the ``-qh``, ``-qk``, and
``-ql`` options, each supplied as three numbers: the minimum value, the
step size, and the maximum value (all in reciprocal lattice units). If
these options are omitted, the grid stored in the parent file is used.

``-R / --regular`` produces a transform using all data without masking.
``-M / --mask`` produces a second transform in which the voxels
identified by ``nxprepare`` are excluded, leaving only the diffuse
signal between the Bragg peaks. Both flags may be given simultaneously,
producing two separate output files.

.. code-block::

    usage: nxtransform [-h] -d DIRECTORY [-e ENTRIES [ENTRIES ...]]
                       [-qh QH QH QH] [-qk QK QK QK] [-ql QL QL QL]
                       [-R] [-M] [-s SUBENTRY] [-o] [-q]

    Perform CCTW transform

    options:
      -h, --help            show this help message and exit
      -d, --directory DIRECTORY
                            scan directory
      -e, --entries ENTRIES [ENTRIES ...]
                            names of entries to be processed
      -qh QH QH QH          Qh - min, step, max
      -qk QK QK QK          Qk - min, step, max
      -ql QL QL QL          Ql - min, step, max
      -R, --regular         perform regular transform
      -M, --mask            perform transform with 3D mask
      -s, --subentry SUBENTRY
                            subentry to be processed
      -o, --overwrite       overwrite existing transforms
      -q, --queue           add to server task queue

nxcombine
---------
``nxcombine`` merges the individual per-entry transforms — one for each
rotation scan entry in the wrapper file — into a single
three-dimensional reciprocal-space map. It invokes CCTW's ``merge``
operation with unit normalization so that overlapping voxels from
different entries are averaged. Both the regular (unmasked) and the
masked transforms can be combined independently by supplying the
``-R / --regular`` and ``-M / --mask`` flags respectively.

.. code-block::

    usage: nxcombine [-h] [-d DIRECTORY] [-e ENTRIES [ENTRIES ...]]
                     [-R] [-M] [-o] [-q]

    Combine CCTW transforms

    options:
      -h, --help            show this help message and exit
      -d, --directory DIRECTORY
                            scan directory
      -e, --entries ENTRIES [ENTRIES ...]
                            names of entries to be combined.
      -R, --regular         combine transforms
      -M, --mask            combine transforms with 3D mask
      -o, --overwrite       overwrite existing transform
      -q, --queue           add to server task queue

nxpdf
-----
``nxpdf`` computes the 3D-ΔPDF (difference Patterson map) from the
combined reciprocal-space data produced by ``nxcombine``. The
calculation proceeds in four steps:

1. **Symmetrize.** All symmetry-equivalent voxels are averaged
   according to the crystal's Laue group, enforcing the expected
   reciprocal-space symmetry and improving statistics in each unique
   region.

2. **Total PDF.** A spherical Tukey taper is applied to the
   symmetrized data to suppress Fourier truncation artefacts, and a
   three-dimensional Fourier transform produces the total PDF in real
   space.

3. **Punch-and-fill.** The intensity within an ellipsoidal volume
   around each Bragg reflection is removed ("punched") and the
   resulting gap is filled by harmonic Laplace interpolation, using
   the Julia ``LaplaceInterpolation.jl`` library. The result is a
   reciprocal-space dataset containing only diffuse signal.

4. **Delta-PDF.** A Fourier transform of the punch-and-filled dataset
   yields the 3D-ΔPDF.

The ``-l / --laue`` option specifies the Laue group symbol to use for
symmetrization; if omitted, the value stored in the NeXus file is used.
The ``-r / --radius`` option sets the radius (in Å⁻¹) of the
ellipsoidal volume removed around each Bragg peak. The ``-Q / --Qmax``
option sets the maximum Q (in Å⁻¹) of the spherical Tukey taper applied
before each Fourier transform.

As with ``nxtransform`` and ``nxcombine``, ``-R / --regular`` and
``-M / --mask`` select whether to compute the PDF from the unmasked or
the masked transform (or both).

.. code-block::

    usage: nxpdf [-h] -d DIRECTORY [-l [LAUE]] [-r RADIUS] [-Q QMAX]
                 [-R] [-M] [-o] [-q]

    Calculate PDF transforms

    options:
      -h, --help            show this help message and exit
      -d, --directory DIRECTORY
                            scan directory
      -l, --laue [LAUE]     Laue group to be used if different from file
      -r, --radius RADIUS   radius of punched holes in Å-1
      -Q, --Qmax QMAX       Maximum Q in Å-1 used in PDF tapers
      -R, --regular         Calculate using regular transforms
      -M, --mask            Calculate using masked transforms
      -o, --overwrite       overwrite existing transforms
      -q, --queue           add to server task queue

nxsum
-----
``nxsum`` adds raw detector frames from two or more scan directories
together pixel-by-pixel, accumulating their monitor counts as well.
This is used when several separate acquisitions that cover the same
rotation range need to be combined before the main reduction workflow
— for example, to build up sufficient counting statistics from shorter
individual scans. The summed data are written to a new scan directory
that is subsequently processed with the standard workflow
(``nxlink``, ``nxmax``, *etc.*).

The ``-c / --create`` flag initializes the new scan directory and
wrapper file; the ``-s / --scans`` option (required) lists the
individual source scan directories. The ``-u / --update`` flag
recalculates the monitor sums without re-copying the raw detector data,
which is useful when only the metadata needs refreshing.

.. code-block::

    usage: nxsum [-h] -d DIRECTORY [-c] [-e ENTRIES [ENTRIES ...]]
                 -s SCANS [SCANS ...] [-u] [-o]

    Sum raw data files

    options:
      -h, --help            show this help message and exit
      -d, --directory DIRECTORY
                            directory containing summed files
      -c, --create          create the sum file and directory
      -e, --entries ENTRIES [ENTRIES ...]
                            names of entries to be summed
      -s, --scans SCANS [SCANS ...]
                            list of scan directories to be summed
      -u, --update          update links to existing summed files
      -o, --overwrite       overwrite existing summed files

.. _nxserver:

nxserver
--------
``nxserver`` manages the asynchronous task server that executes
workflow steps submitted with the ``--queue`` flag. Starting the server
puts it into the background, where it continuously dequeues and runs
tasks as they arrive. The positional ``command`` argument accepts:

``start``
    Launch the server process.
``stop``
    Gracefully shut down the server after finishing the current task.
``status``
    Print whether the server is running and how many tasks are queued.
``clear``
    Remove all pending tasks from the queue without running them.
``kill``
    Immediately terminate the server process.

The ``-t / --type`` option selects the execution backend: ``multicore``
runs all tasks on the local machine using multiple CPU cores, while
``multinode`` distributes tasks across compute nodes using Parsl. The
``-c / --cores`` option controls the number of parallel workers.

.. code-block::

    usage: nxserver [-h] [-d [DIRECTORY]] [-t TYPE] [-c CORES] [command]

    Launch server for data reduction workflow

    positional arguments:
      command               valid commands are: status|start|stop|clear|kill

    options:
      -h, --help            show this help message and exit
      -d, --directory [DIRECTORY]
                            Start the server in this directory
      -t, --type TYPE       Server type: multicore|multinode|direct
      -c, --cores CORES     Number of cores

nxreduce
--------
``nxreduce`` is a convenience wrapper that chains any combination of
workflow steps in a single command. Each step is selected with a
single-letter flag; multiple flags can be combined to run a pipeline
without invoking individual scripts. If ``--queue`` is given, all
selected steps are submitted to the server together.

.. code-block::

    usage: nxreduce [-h] -d DIRECTORY [-e ENTRIES [ENTRIES ...]] [-s SUBENTRY]
                    [-L] [-l] [-m] [-f] [-r] [-p] [-t] [-C] [-P]
                    [-R] [-M] [-o] [-q]

    Perform data reduction on entries

    options:
      -h, --help            show this help message and exit
      -d, --directory DIRECTORY
                            scan directory
      -e, --entries ENTRIES [ENTRIES ...]
                            names of entries to be processed
      -s, --subentry SUBENTRY
                            subentry to be processed
      -L, --load            load raw data
      -l, --link            link wrapper file to raw data
      -m, --max             find maximum counts
      -f, --find            find peaks
      -r, --refine          refine lattice parameters
      -p, --prepare         prepare 3D masks
      -t, --transform       perform CCTW transforms
      -C, --combine         combine CCTW transforms
      -P, --pdf             perform PDF transforms
      -R, --regular         perform regular CCTW transforms
      -M, --mask            perform CCTW transforms with 3D mask
      -o, --overwrite       overwrite existing maximum
      -q, --queue           add to server task queue
