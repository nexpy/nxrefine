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

nxload
------
Load data

.. code-block:: 

    usage: nxload [-h] -d DIRECTORY [-e ENTRIES [ENTRIES ...]] [-o] [-q]

    Load raw data

    optional arguments:
      -h, --help            show this help message and exit
      -d DIRECTORY, --directory DIRECTORY
                            scan directory
      -e ENTRIES [ENTRIES ...], --entries ENTRIES [ENTRIES ...]
                            names of entries to be loaded
      -o, --overwrite       overwrite existing peaks
      -q, --queue           add to server task queue

nxlink
------
Link metadata

.. code-block:: 

    usage: nxlink [-h] -d DIRECTORY [-e ENTRIES [ENTRIES ...]] [-o] [-q]

    Link data and metadata to NeXus file

    optional arguments:
      -h, --help            show this help message and exit
      -d DIRECTORY, --directory DIRECTORY
                            scan directory
    -e ENTRIES [ENTRIES ...], --entries ENTRIES [ENTRIES ...]
                            names of entries to be searched
    -o, --overwrite         overwrite existing peaks
    -q, --queue             add to server task queue

nxcopy
------
Copy data

.. code-block:: 

    usage: nxcopy [-h] -d DIRECTORY [-e ENTRIES [ENTRIES ...]] [-p PARENT] [-o] [-q]

    Copy instrument parameters from a parent file

    optional arguments:
      -h, --help            show this help message and exit
      -d DIRECTORY, --directory DIRECTORY
                            scan directory
      -e ENTRIES [ENTRIES ...], --entries ENTRIES [ENTRIES ...]
                            names of entries to be searched
      -p PARENT, --parent PARENT
                            file name of file to copy from
      -o, --overwrite       overwrite existing peaks
      -q, --queue           add to server task queue

nxmax
-----
.. code-block:: 

    usage: nxmax [-h] -d DIRECTORY [-e ENTRIES [ENTRIES ...]] [-f FIRST] [-l LAST] [-o] [-m] [-q]

    Find maximum counts of the signal in the specified path

    optional arguments:
      -h, --help            show this help message and exit
      -d DIRECTORY, --directory DIRECTORY
                            scan directory
      -e ENTRIES [ENTRIES ...], --entries ENTRIES [ENTRIES ...]
                            names of entries to be processed
      -f FIRST, --first FIRST
                            first frame
      -l LAST, --last LAST  last frame
      -o, --overwrite       overwrite existing maximum
      -m, --monitor         monitor progress in the command line
      -q, --queue           add to server task queue

nxfind
------

.. code-block:: 

    usage: nxfind [-h] -d DIRECTORY [-e ENTRIES [ENTRIES ...]] [-t THRESHOLD] [-f FIRST] [-l LAST] [-P PIXELS] [-o] [-p PARENT] [-m] [-q]

    Find peaks within the NeXus data

    optional arguments:
      -h, --help            show this help message and exit
      -d DIRECTORY, --directory DIRECTORY
                            scan directory
      -e ENTRIES [ENTRIES ...], --entries ENTRIES [ENTRIES ...]
                            names of entries to be searched
      -t THRESHOLD, --threshold THRESHOLD
                            peak threshold
      -f FIRST, --first FIRST
                            first frame
      -l LAST, --last LAST  last frame
      -P PIXELS, --pixels PIXELS
                            minimum pixels between peaks
      -o, --overwrite       overwrite existing peaks
      -p PARENT, --parent PARENT
                            The parent .nxs file to use
      -m, --monitor         monitor progress in the command line
      -q, --queue           add to server task queue


nxrefine
--------

.. code-block:: 

    usage: nxrefine [-h] -d DIRECTORY [-e ENTRIES [ENTRIES ...]] [-l] [-p POLAR_MAX] [-T HKL_TOLERANCE] [-o] [-q]

    Refine lattice parameters and goniometer angles

    optional arguments:
      -h, --help            show this help message and exit
      -d DIRECTORY, --directory DIRECTORY
                            scan directory
      -e ENTRIES [ENTRIES ...], --entries ENTRIES [ENTRIES ...]
                            names of entries to be processed
      -l, --lattice         refine lattice parameters
      -p POLAR_MAX, --polar_max POLAR_MAX
                            maximum polar angle in degrees
      -T HKL_TOLERANCE, --hkl_tolerance HKL_TOLERANCE
                            tolerance for including peak in Å-1
      -o, --overwrite       overwrite existing maximum
      -q, --queue           add to server task queue

nxprepare
---------

.. code-block:: 

    usage: nxprepare [-h] -d DIRECTORY [-e ENTRIES [ENTRIES ...]] [--t1 T1] [--h1 H1] [--t2 T2] [--h2 H2] [-o] [-m] [-q]

    Prepare 3D mask around Bragg peaks

    optional arguments:
      -h, --help            show this help message and exit
      -d DIRECTORY, --directory DIRECTORY
                            scan directory
      -e ENTRIES [ENTRIES ...], --entries ENTRIES [ENTRIES ...]
                            names of entries to be processed
      --t1 T1               threshold for smaller convolution
      --h1 H1               size of smaller convolution
      --t2 T2               threshold for larger convolution
      --h2 H2               size of larger convolution
      -o, --overwrite       overwrite existing mask
      -m, --monitor         monitor progress in the command line
      -q, --queue           add to server task queue

nxtransform
-----------

.. code-block:: 

    usage: nxtransform [-h] -d DIRECTORY [-e ENTRIES [ENTRIES ...]] [-qh QH QH QH] [-qk QK QK QK] [-ql QL QL QL] [-R] [-M] [-o] [-q]

    Perform CCTW transform

    optional arguments:
      -h, --help            show this help message and exit
      -d DIRECTORY, --directory DIRECTORY
                            scan directory
      -e ENTRIES [ENTRIES ...], --entries ENTRIES [ENTRIES ...]
                            names of entries to be processed
      -qh QH QH QH          Qh - min, step, max
      -qk QK QK QK          Qk - min, step, max
      -ql QL QL QL          Ql - min, step, max
      -R, --regular         perform regular transform
      -M, --mask            perform transform with 3D mask
      -o, --overwrite       overwrite existing transforms
      -q, --queue           add to server task queue


nxcombine
---------

.. code-block:: 

    usage: nxcombine [-h] [-d DIRECTORY] [-e ENTRIES [ENTRIES ...]] [-R] [-M] [-o] [-q]

    Combine CCTW transforms

    optional arguments:
      -h, --help            show this help message and exit
      -d DIRECTORY, --directory DIRECTORY
                            scan directory
      -e ENTRIES [ENTRIES ...], --entries ENTRIES [ENTRIES ...]
                            names of entries to be combined.
      -R, --regular         combine transforms
      -M, --mask            combine transforms with 3D mask
      -o, --overwrite       overwrite existing transform
      -q, --queue           add to server task queue


nxpdf
-----

.. code-block:: 

    usage: nxpdf [-h] -d DIRECTORY [-l [LAUE]] [-r RADIUS] [-Q QMAX] [-R] [-M] [-o] [-q]

    Calculate PDF transforms

    optional arguments:
      -h, --help            show this help message and exit
      -d DIRECTORY, --directory DIRECTORY
                            scan directory
      -l [LAUE], --laue [LAUE]
                            Laue group to be used if different from file
      -r RADIUS, --radius RADIUS
                            radius of punched holes in Å-1
      -Q QMAX, --Qmax QMAX  Maximum Q in Å-1 used in PDF tapers
      -R, --regular         Calculate using regular transforms
      -M, --mask            Calculate using masked transforms
      -o, --overwrite       overwrite existing transforms
      -q, --queue           add to server task queue


nxserver
--------

.. code-block:: 

    usage: nxserver [-h] [-d [DIRECTORY]] [-t TYPE] [-n NODES [NODES ...]] [-c CORES] [-r REMOVE [REMOVE ...]] [command]

    Launch server for data reduction workflow

    positional arguments:
      command               status|start|stop|list|clear|kill

    optional arguments:
      -h, --help            show this help message and exit
      -d [DIRECTORY], --directory [DIRECTORY]
                            Start the server in this directory
      -t TYPE, --type TYPE  Server type: multicore|multinode
      -n NODES [NODES ...], --nodes NODES [NODES ...]
                            Add nodes
      -c CORES, --cores CORES
                            Number of cores
      -r REMOVE [REMOVE ...], --remove REMOVE [REMOVE ...]
                            Remove nodes


