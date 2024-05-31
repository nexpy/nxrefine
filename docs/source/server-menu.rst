Server Menu
===========
The *NXRefine* plugin to *NeXpy* installs a top-level menu labelled
"Server", which is used to launch and monitor data reduction operations performed as part of the workflow.

Manage Workflows
----------------
This dialog initializes a new experiment directory layout using the
server settings to initialize default locations. When the dialog is
launched, click on "Choose Experiment Directory" to launch the system
file browser in order to select or create the new experiment  directory.


Copy Parameters
---------------
This dialog creates NeXus files that are used as templates for the
experimental files that are used to store all the data and metadata
associated with a particular set of rotation scans. The initial metadata
is defined by parameters in the settings file in the ``tasks``
sub-directory, which can be modified by the "Edit Settings" sub-menu
described below. However, some of the metadata will be refined using a
powder calibration, whose results are then stored in this file.

Manage Server
-------------
This dialog will import a TIFF or CBF file containing measurements of a
powder calibrant and refine the detector position and coordinates, using
the *PyFAI* API. Alternatively, if the calibration parameters are
already available in a PONI file, they can be directly imported. The
resulting powder data and calbration parameters are then saved to the
configuration template previously created using the *New Configuration*
dialog.
