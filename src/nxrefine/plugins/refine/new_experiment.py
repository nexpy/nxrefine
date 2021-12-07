# -----------------------------------------------------------------------------
# Copyright (c) 2015-2021, NeXpy Development Team.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file COPYING, distributed with this software.
# -----------------------------------------------------------------------------

import os

from nexpy.gui.datadialogs import GridParameters, NXDialog
from nexpy.gui.utils import report_error
from nexusformat.nexus import NeXusError
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
        self.parameters = GridParameters()
        self.parameters.add('experiment', 'experiment', 'Experiment')

        self.set_layout(
            self.directorybox('Choose Home Directory', default=False),
            self.parameters.grid(header=False),
            self.close_layout(save=True))
        self.set_title('New Experiment')

    def accept(self):
        try:
            home_directory = self.get_directory()
            experiment_directory = os.path.join(
                home_directory, self.parameters['experiment'].value)
            if not os.path.exists(experiment_directory):
                os.makedirs(experiment_directory)
            self.mainwindow.default_directory = experiment_directory
            configuration_directory = os.path.join(experiment_directory,
                                                   'configurations')
            if not os.path.exists(configuration_directory):
                os.makedirs(configuration_directory)
            task_directory = os.path.join(experiment_directory, 'tasks')
            if not os.path.exists(task_directory):
                os.makedirs(task_directory)
            nxdb = NXDatabase(os.path.join(task_directory, 'nxdatabase.db'))
            calibration_directory = os.path.join(experiment_directory,
                                                 'calibrations')
            if not os.path.exists(calibration_directory):
                os.makedirs(calibration_directory)
            script_directory = os.path.join(experiment_directory, 'scripts')
            if not os.path.exists(script_directory):
                os.makedirs(script_directory)
            super().accept()
        except Exception as error:
            report_error("Defining New Experiment", error)
