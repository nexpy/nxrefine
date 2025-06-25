# -----------------------------------------------------------------------------
# Copyright (c) 2022, Argonne National Laboratory.
#
# Distributed under the terms of an Open Source License.
#
# The full license is in the file LICENSE.pdf, distributed with this software.
# -----------------------------------------------------------------------------

from pathlib import Path

from nexpy.gui.dialogs import NXDialog
from nexpy.gui.utils import display_message, report_error
from nexpy.gui.widgets import NXLabel
from nexusformat.nexus import NeXusError
from nxrefine.nxbeamline import get_beamline
from nxrefine.nxsettings import NXSettings


def show_dialog():
    try:
        dialog = ImportScanDialog()
        dialog.show()
    except NeXusError as error:
        report_error("Importing Data", error)


class ImportScanDialog(NXDialog):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.directory_box = self.directorybox('Choose Experiment Directory',
                                               self.choose_directory,
                                               default=False)
        self.set_layout(self.directory_box, self.close_buttons(save=True))
        self.set_title('Import Scans')

    def choose_directory(self):
        super().choose_directory()

        settings = NXSettings().settings
        self.analysis_path = settings['instrument']['analysis_path']

        settings = NXSettings(self.experiment_directory).settings
        self.analysis_home = Path(settings['instrument']['analysis_home'])
        self.raw_home = Path(settings['instrument']['raw_home'])
        self.raw_path = settings['instrument']['raw_path']
        self.beamline = get_beamline(settings['instrument']['instrument'])

        if not self.raw_directory.exists():
            display_message(
                "Importing Data",
                f"Raw directory '{self.raw_directory}' does not exist.")
            return

        self.sample_box = self.select_box(self.get_samples())
        self.sample_layout = self.make_layout(
            NXLabel("Sample: "), self.sample_box)
        self.insert_layout(1, self.sample_layout)
        self.configuration_box = self.select_box(self.get_configurations())
        self.configuration_layout = self.make_layout(
            NXLabel("Configuration: "), self.configuration_box)
        self.insert_layout(2, self.configuration_layout)
        self.insert_layout(
            3, self.checkboxes(('overwrite', 'Overwrite Existing Files',
                                False)))
        self.activate()

    @property
    def experiment(self):
        if self.experiment_directory.name == self.analysis_path:
            return self.experiment_directory.parent.name
        else:
            return self.experiment_directory.name

    @property
    def experiment_directory(self):
        directory = Path(self.get_directory())
        if self.analysis_path and directory.name != self.analysis_path:
            analysis_directory = directory / self.analysis_path
            if analysis_directory.exists():
                return analysis_directory
        return directory

    @property
    def raw_directory(self):
        return self.raw_home / self.experiment / self.raw_path

    @property
    def sample(self):
        return Path(self.sample_box.currentText()).parent.name

    @property
    def label(self):
        return Path(self.sample_box.currentText()).name

    @property
    def overwrite(self):
        return self.checkbox['overwrite'].isChecked()

    def get_samples(self):
        if self.raw_directory.exists():
            sample_directories = [f for f in self.raw_directory.iterdir()
                                  if f.is_dir()]
        else:
            return []
        samples = []
        for sample_directory in sample_directories:
            label_directories = [f for f in sample_directory.iterdir()
                                 if f.is_dir()]
            for label_directory in label_directories:
                samples.append(label_directory.relative_to(self.raw_directory))
        return [str(sample) for sample in samples]

    def get_configurations(self):
        directory = self.experiment_directory / 'configurations'
        if directory.exists():
            return sorted([str(f.name) for f in directory.glob('*.nxs')])
        else:
            return []

    @property
    def configuration_file(self):
        return (self.experiment_directory / 'configurations' /
                self.configuration_box.currentText())

    def accept(self):
        sample_directory = self.experiment_directory / self.sample / self.label
        sample_directory.mkdir(parents=True, exist_ok=True)
        try:
            self.beamline(directory=sample_directory).import_data(
                self.configuration_file, overwrite=self.overwrite)
            super().accept()
        except NeXusError as error:
            report_error("Importing Data", error)
