Sample Refinement
*****************
When a new sample has been mounted and the first scan collected,
*NXRefine* provides a set of tools to prepare the data for
transformation into S(**Q**). These are normally run using *NeXpy*
dialogs accessible from the :ref:`Refine Menu` described below, which
are used to select parameters for use in the data reduction, perform an
analysis of all the collected frames in order to enable, for example,
absorption corrections for each frame and other diagnostic information,
launch a peak search function to identify all the Bragg peaks embedded
in the data, define the sample space group, determine and optimize the
sample orientation based on the Bragg peak assignments, and generate the
Q-mesh used when transforming the data to reciprocal space. Typically,
these steps are performed after the first sample rotation scan, often at
room temperature or while the sample is cooling. The results of this
process are stored in the associated NeXus scan file, which then is
designated the "parent" file, from which all the other scans copy their
initial orientation before the automated refinement. This allows the
data from the remaining scans to be reduced by the automated workflow.

The only requirement is that the parent shares the same space group as
the scans that are reduced by the automated workflow. The unit cell
parameters and orientation matrix are refined by a least-squares
optimization of the Bragg peak locations identified in each new scan.
If there is a significant change in the space group at a structural
phase transition, it may be necessary to define a different scan file as
the parent for scans performed above or below the transition.

In this section, we will describe the structure of the NeXus files as well as details of how the *NeXpy* GUI dialogs in the :ref:`Refine
Menu` can be used to prepare the files for subsequent analyis.

.. figure:: /images/scan-file.png
   :align: right
   :width: 90%
   :figwidth: 40%

NeXus files
===========
The scan files are stored using the hierarchical `NeXus format
<http://www.nexusformat.org/>`__, in which the data for each scan are stored in groups, or entries, conforming to the `NXentry` base class. There is one entry for each sample rotation scan, usually labelled `f1`, `f2`, `f3`, *etc.*, although the number of such scans can vary. There is also a top-level entry (called 'entry'), which contains the metadata that is common to all the rotation scans, as well as the results of merging the reduced data from each one.

In the example on the right, most of the items are also groups corresponding to different base classes, that contain either raw data, reduced data, metadata, or information resulting from each component of the workflow. When the NeXus file is loaded into NeXpy, its contents can be inspected in a tree view, such as the one shown here. Here are a few examples.

:instrument: This is a group that contains instrumental parameters, such
             as the incident wavelength, detector distance, goniometer
             angles, and attenuators. It also stores the powder
             calibration data and parameters.

:sample: This group contains the sample information, including the
         chemical formula, unit cell parameters, space and Laue groups,
         and sample environment parameters, such as temperature.
         *NXRefine* assumes that the sample parameters are independent
         of the particular rotation scan, so all the sample groups are
         linked to the one stored in the 'entry' group.

There are a number of groups that contain the results of some of the analysis.

:peaks: This group contains the results of all the Bragg peaks
        identified by the peak search, such as their pixel coordinates
        on the detector, their polar and azimuthal angles, and
        intensities. These are used to determine the sample orientation
        matrix. The group 




Refine Menu
===========
The *NXRefine* plugin to *NeXpy* installs a top-level menu labelled
"Refine", which initializes parameters required for the data reduction workflow, determines 

Choose Parameters
-----------------
This dialog allows the parameters used in the data reduction workflow to
be specified for a particular scan file.

.. figure:: /images/choose-parameters.png
   :align: center
   :width: 80%

The following parameters are defined.

:Peak Threshold: This defines the minimum intensity used to identify a
                 scattering feature as a potential Bragg peak. In the
                 :ref:`Find Peaks` algorithm, a first-moment analysis is
                 performed on peaks that exceed this threshold, with
                 Bragg peaks on successive frames merged to form one
                 peak. 

:First Frame: This is the first frame in the rotation scan to be 
              included in subsequent analyses. The default is 10.

:Last Frame: This is the last frame in the rotation scan to be included 
             in subsequent analyses. The default is 3640, based on the assumption that a complete rotation contains 3650 frames.

:Max. Polar Angle: This is the maximum scattering angle that is to be 
                   included in refinments of the orientation matrix.

:analysis_path: This is the path within the experiment directory to the
                *NXRefine* sub-directories. In the above example, this
                would be ``nxrefine``.



Copy Parameters
---------------
This dialog allows parameters to be copied from a parent scan file.

Find Maximum
------------
This dialog will import a TIFF or CBF file containing measurements of a
powder calibrant and refine the detector position and coordinates, using
the *PyFAI* API. Alternatively, if the calibration parameters are
already available in a PONI file, they can be directly imported. The
resulting powder data and calbration parameters are then saved to the
configuration template previously created using the *New Configuration*
dialog.

.. figure:: /images/calibrate-powder.png
   :align: center
   :width: 80%

Find Peaks
----------
This dialog creates a pixel mask that is used to exclude bad pixels from
further analysis. As described above, when a new configuration file is
created, a pixel mask that excludes gaps between detector chips is
automatically added. Additional pixels can be excluded using this
dialog, either by adding editable shapes that are constructively added
to the existing mask or by importing the mask from an external file,
which can store the mask in any image format. The latter is useful if a
beamline regularly updates a particular detector's mask as bad pixels are identified.

Prepare 3D Mask
---------------
This dialog has the single purpose of creating a directory tree for a
new sample. The dialog enables the creation of a sample directory within
the requested experiment directory and a sub-directory with a unique
label for each instance of that sample measured during an experiment.

.. figure:: /images/new-sample.png
   :align: center
   :width: 60%

Calculate Angles
----------------
This dialog is used to create a NeXus file in preparation for an
experimental measurement. The file will be based on the selected
configuration file and be saved in the specified sample/label directory.
The name of the file will be "<sample>_<scan>.nxs", where <scan> is the
Scan Label specified in the dialog ('300K' in the image below).

Define Lattice
--------------
This dialog is for instruments in which the scans are already defined
using different methods to those above. For example, on the QM2
instrument at CHESS, the scans are defined in SPEC files, with the data
stored separately in a separate read-only directory. With this dialog,
the directories containing the raw images are associated with the
corresponding SPEC scan, allowing NeXus files to be automatically
generated. This customization is encoded in a QM2 sub-class of the
``NXBeamLine`` class, which is installed separately as a NXRefine
plugin. The process for customizing other beamlines is described later.

Refine Lattice
--------------
This dialog allows data in NeXus files collected under identical
conditions to be summed to produce a single NeXus file that can be
processed using the usual workflow.

Transform Data
--------------
This dialog allows the settings, whose default values are defined in the
server directory (see :ref:`default_settings`), to be customized for the
data reduction performed in the selected experiment. The settings are
stored in ``<experiment>/tasks/settings.ini``. The meanings of each
setting are described in the next section.
