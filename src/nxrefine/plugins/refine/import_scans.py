# -----------------------------------------------------------------------------
# Copyright (c) 2015-2023, NeXpy Development Team.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file COPYING, distributed with this software.
# -----------------------------------------------------------------------------

from pathlib import Path

from nexpy.gui.datadialogs import NXDialog
from nexpy.gui.utils import display_message, report_error
from nexpy.gui.widgets import NXLabel
from nexusformat.nexus import NeXusError
from nxrefine.nxbeamline import get_beamline
from nxrefine.nxsettings import NXSettings


def show_dialog():
    try:
        dialog = ImportDialog()
        dialog.show()
    except NeXusError as error:
        report_error("Importing Data", error)


class ImportDialog(NXDialog):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.directory_box = self.directorybox('Choose Experiment Directory',
                                               self.choose_directory,
                                               default=False)
        self.set_layout(self.directory_box, self.close_buttons(save=True))
        self.set_title('Import Scans')

    def choose_directory(self):
        super().choose_directory()
        directory = self.get_directory()
        if directory:
            self.home_directory = Path(directory)
        else:
            return
        settings = NXSettings(self.home_directory).settings
        self.beamline = get_beamline(settings['instrument']['instrument'])
        if not self.beamline.import_data_enabled:
            display_message(
                "Importing Data",
                f"Importing data not implemented for {self.beamline.name}")
            self.reject()

        analysis_home = Path(settings['instrument']['analysis_home'])
        if analysis_home not in self.home_directory.parents:
            display_message(
                "Importing Data",
                f"Chosen directory not relative to '{analysis_home}'.")
            return
        analysis_path = settings['instrument']['analysis_path']
        if analysis_path and self.home_directory.name != analysis_path:
            self.home_directory = self.home_directory / analysis_path
        experiment = self.home_directory.parent.relative_to(analysis_home)
        raw_home = Path(settings['instrument']['raw_home'])
        raw_path = settings['instrument']['raw_path']
        self.raw_directory = raw_home / experiment / raw_path
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
        directory = self.home_directory / 'configurations'
        if directory.exists():
            return sorted([str(f.name) for f in directory.glob('*.nxs')])
        else:
            return []

    @property
    def configuration_file(self):
        return (self.home_directory / 'configurations' /
                self.configuration_box.currentText())

    def accept(self):
        sample_directory = self.home_directory / self.sample / self.label
        sample_directory.mkdir(parents=True, exist_ok=True)
        try:
            self.beamline(directory=sample_directory).import_data(
                self.configuration_file, overwrite=self.overwrite)
            super().accept()
        except NeXusError as error:
            report_error("Importing Data", error)
