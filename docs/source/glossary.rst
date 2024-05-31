Glossary of Terms
*****************
This section contains a list of terms used in the preceding sections of the documentation, along with brief descriptions and links to where they are explained in more detail.

**Experiment**
  Each experiment consists of measurements performed within a specific
  time period, which share a common set of instrument configurations and
  calibration files. The measurements could be performed on multiple
  samples.

  .. seealso:: :ref:`Experiment Layout`

**Experiment Directory**
  This is the directory containing all the files and sub-directories associated with a single experiment.

**Sample**
  Each experiment typcially contains measurements on one or more
  samples, which are labelled by their chemical formula or a descriptive
  name, *e.g.,* "TiSe2" or "LBCO". It is common to perform measurements
  on multiple crystals that are nominally the same material, each with a
  unique label, *e.g.*, defined by the crystal grower, before deciding which crystal to use.

**Sample Directory**
  In the "Experiment Directory", each sample has its own sub-directory, within which are one or more sub-directories for each measured crystal. For example, in the following directory tree, there are two possible "Sample Directories", either ``experiment/sample/label1`` or ``experiment/sample/label2``::

    experiment
    └── sample
        └── label1
        └── label2

**Scan File**
  This is the NeXus file that contains all the information required to reduce, analyze, and interpret the data measured at a single temperature or other instrumental setting. This is stored in one of the "Sample Directories", with a name given by combining the sample name and scan parameter, *e.g.* for measurements at 100K, the following NeXus file is defined.::

    experiment
    └── sample
        └── label
            └── sample_100K.nxs

**Scan Directory**
  Each NeXus file contains external links to HDF5 files containing the raw data and larger processed data files. These are stored in "Scan Directories", whose names must match the corresponding "Scan File"::
 
    experiment
    └── sample
        └── label
            ├── sample_100K.nxs
            └── 100K
                ├── f1.h5
                ...

**Server Directory**
  This directory is defined when *NXRefine* is first installed in order to store log files, task queues, and default settings. On systems with multiple users, this must be in a shared location. It is recommended that all users are members of the same group, which has read/write privileges in the "Server Directory".

  .. seealso:: :ref:`Server Management`

