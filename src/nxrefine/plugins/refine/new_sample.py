from __future__ import unicode_literals
import os

from nexusformat.nexus import NeXusError
from nexpy.gui.datadialogs import BaseDialog, GridParameters
from nexpy.gui.utils import report_error


def show_dialog():
    try:
        dialog = SampleDialog()
        dialog.show()
    except NeXusError as error:
        report_error("Defining New Sample", error)


class SampleDialog(BaseDialog):

    def __init__(self, parent=None):
        super(SampleDialog, self).__init__(parent)

        self.sample = GridParameters()
        self.sample.add('sample', 'sample', 'Sample Name')
        self.sample.add('label', 'label', 'Sample Label')

        self.set_layout(self.directorybox('Choose Experiment Directory'), 
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
        super(SampleDialog, self).accept()
