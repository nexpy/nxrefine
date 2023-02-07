# -----------------------------------------------------------------------------
# Copyright (c) 2015-2021, NeXpy Development Team.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file COPYING, distributed with this software.
# -----------------------------------------------------------------------------

from pathlib import Path

from nexpy.gui.datadialogs import GridParameters, NXDialog
from nexpy.gui.utils import display_message, report_error
from nexusformat.nexus import NeXusError
from nxrefine.nxbeamline import get_beamline
from nxrefine.nxdatabase import NXDatabase


def show_dialog():
    try:
        dialog = ExperimentDialog()
        dialog.show()
    except NeXusError as error:
        report_error("Defining New Experiment", error)


class ExperimentDialog(NXDialog):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.beamline = get_beamline()
        if self.beamline.experiment_directory_exists:
            self.set_layout(
                self.directorybox('Choose Home Directory', default=False),
                self.close_layout(save=True))
        else:
            self.parameters = GridParameters()
            self.parameters.add('experiment', 'experiment', 'Experiment')
            self.set_layout(
                self.directorybox('Choose Home Directory', default=False),
                self.parameters.grid(header=False),
                self.close_layout(save=True))
        self.set_title('New Experiment')

    def choose_directory(self):
        super().choose_directory()
        self.directory = Path(self.get_directory())
        self.is_valid_directory()

    def is_valid_directory(self):
        if self.directory.is_relative_to(self.beamline.experiment_home):
            return True
        else:
            display_message("Importing Data",
                            "Home directory must be relative to "
                            f"{self.beamline.experiment_home}")
            return False

    def accept(self):
        if not self.is_valid_directory():
            return
        try:
            if (self.beamline.experiment_directory_exists
                    and self.directory.name != 'nxrefine'):
                experiment_directory = self.directory / 'nxrefine'
            else:
                experiment_directory = (self.directory /
                                        self.parameters['experiment'].value)
            experiment_directory.mkdir(exist_ok=True)
            self.mainwindow.default_directory = str(experiment_directory)
            configuration_directory = experiment_directory / 'configurations'
            configuration_directory.mkdir(exist_ok=True)
            task_directory = experiment_directory / 'tasks'
            task_directory.mkdir(exist_ok=True)
            _ = NXDatabase(task_directory / 'nxdatabase.db')
            calibration_directory = experiment_directory / 'calibrations'
            calibration_directory.mkdir(exist_ok=True)
            script_directory = experiment_directory / 'scripts'
            script_directory.mkdir(exist_ok=True)
            super().accept()
        except Exception as error:
            report_error("Defining New Experiment", error)
