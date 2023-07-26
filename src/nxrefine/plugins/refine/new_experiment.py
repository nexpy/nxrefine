# -----------------------------------------------------------------------------
# Copyright (c) 2015-2021, NeXpy Development Team.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file COPYING, distributed with this software.
# -----------------------------------------------------------------------------

from pathlib import Path

from nexpy.gui.datadialogs import NXDialog
from nexpy.gui.pyqt import QtWidgets
from nexpy.gui.utils import report_error
from nexpy.gui.widgets import NXLineEdit, NXPushButton
from nexusformat.nexus import NeXusError
from nxrefine.nxbeamline import get_beamline
from nxrefine.nxdatabase import NXDatabase
from nxrefine.nxsettings import NXSettings


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
        if self.beamline.raw_home.exists():
            raw_text = str(self.beamline.raw_home.resolve())
        else:
            raw_text = None
        self.raw_button = NXPushButton('Choose Raw Directory',
                                       slot=self.choose_raw_directory)
        self.raw_box = NXLineEdit(raw_text, parent=self, width=300)
        self.raw_layout = self.make_layout(self.raw_button, self.raw_box)
        if self.beamline.experiment_home.exists():
            exp_text = str(self.beamline.experiment_home.resolve())
        else:
            exp_text = None
        self.exp_button = NXPushButton('Choose Experiment Directory',
                                       slot=self.choose_exp_directory)
        self.exp_box = NXLineEdit(exp_text, parent=self, width=300)
        self.exp_layout = self.make_layout(self.exp_button, self.exp_box)
        self.set_layout(
            self.raw_layout,
            self.exp_layout,
            self.close_layout(save=True))
        self.set_title('New Experiment')

    def choose_raw_directory(self):
        directory = QtWidgets.QFileDialog.getExistingDirectory(
            self, 'Choose Raw Directory', self.raw_box.text())
        if Path(directory).exists():
            self.raw_box.setText(str(directory))
        if not self.exp_box.text():
            self.exp_box.setText(str(self.raw_directory))

    @property
    def raw_directory(self):
        return Path(self.raw_box.text())

    def choose_exp_directory(self):
        directory = QtWidgets.QFileDialog.getExistingDirectory(
            self, 'Choose Experiment Directory', self.exp_box.text())
        if Path(directory).exists():
            self.exp_box.setText(str(directory))

    @property
    def exp_directory(self):
        if (self.checkbox['nxrefine'].isChecked()
                and not self.exp_box.text().endswith('nxrefine')):
            return Path(self.exp_box.text()) / 'nxrefine'
        else:
            return Path(self.exp_box.text())

    def accept(self):
        try:
            experiment_path = self.exp_directory
            raw_path = self.raw_directory
            experiment_path.mkdir(exist_ok=True)
            self.mainwindow.default_directory = str(experiment_path)
            configuration_directory = experiment_path / 'configurations'
            configuration_directory.mkdir(exist_ok=True)
            task_directory = experiment_path / 'tasks'
            task_directory.mkdir(exist_ok=True)
            _ = NXDatabase(task_directory / 'nxdatabase.db')
            settings = NXSettings(task_directory)
            settings.set('instrument', 'raw_path', str(raw_path))
            settings.set('instrument', 'experiment_path', str(experiment_path))
            settings.save()
            calibration_directory = experiment_path / 'calibrations'
            calibration_directory.mkdir(exist_ok=True)
            script_directory = experiment_path / 'scripts'
            script_directory.mkdir(exist_ok=True)
            super().accept()
        except Exception as error:
            report_error("Defining New Experiment", error)
