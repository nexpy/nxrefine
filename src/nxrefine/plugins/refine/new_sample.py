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


def show_dialog():
    try:
        dialog = SampleDialog()
        dialog.show()
    except NeXusError as error:
        report_error("Defining New Sample", error)


class SampleDialog(NXDialog):

    def __init__(self, parent=None):
        super().__init__(parent)

        self.sample = GridParameters()
        self.sample.add('sample', 'sample', 'Sample Name')
        self.sample.add('label', 'label', 'Sample Label')

        self.set_layout(self.directorybox('Choose Experiment Directory',
                                          default=False),
                        self.sample.grid(header=False),
                        self.close_buttons(save=True))

        self.set_title('New Sample')

    def accept(self):
        home_directory = self.get_directory()
        self.mainwindow.default_directory = home_directory
        sample_directory = os.path.join(home_directory,
                                        self.sample['sample'].value,
                                        self.sample['label'].value)
        if not os.path.exists(sample_directory):
            os.makedirs(sample_directory)
        super().accept()
