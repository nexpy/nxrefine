# -----------------------------------------------------------------------------
# Copyright (c) 2018-2026, Argonne National Laboratory.
#
# Distributed under the terms of an Open Source License.
#
# The full license is in the file LICENSE.pdf, distributed with this software.
# -----------------------------------------------------------------------------

from pathlib import Path

from nexpy.gui.dialogs import GridParameters, NXDialog
from nexpy.gui.utils import report_error
from nexusformat.nexus import NeXusError

from nxrefine.nxsettings import NXSettings


def show_dialog():
    try:
        dialog = SampleDialog()
        dialog.show()
    except NeXusError as error:
        report_error("Defining New Sample", error)


class SampleDialog(NXDialog):

    def __init__(self, parent=None):
        super().__init__(parent)

        self.sample_parameters = GridParameters()
        self.sample_parameters.add('sample', 'sample', 'Sample Name')
        self.sample_parameters.add('label', 'label', 'Sample Label')

        settings = NXSettings().settings
        self.default_directory = settings['instrument']['analysis_home']
        self.analysis_path = settings['instrument']['analysis_path']

        self.set_layout(self.directorybox('Choose Experiment Directory',
                                          default=False),
                        self.sample_parameters.grid(header=False),
                        self.action_buttons(('Create Sample Directory',
                                             self.create_sample_directory)),
                        self.close_buttons(close=True))
        self.set_title('New Sample')

    def choose_directory(self):
        if self.default_directory:
            self.set_default_directory(self.default_directory)
        super().choose_directory()

    @property
    def experiment_directory(self):
        directory = Path(self.get_directory())
        if self.analysis_path and directory.name != self.analysis_path:
            directory = directory / self.analysis_path
        return directory

    @property
    def sample(self):
        return self.sample_parameters['sample'].value

    @property
    def label(self):
        return self.sample_parameters['label'].value

    def create_sample_directory(self):
        self.sample_directory = (self.experiment_directory /
                                 self.sample / self.label)
        self.sample_directory.mkdir(parents=True, exist_ok=True)
