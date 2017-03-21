from __future__ import unicode_literals
import os
import numpy as np
from nexusformat.nexus import *
from nexpy.gui.datadialogs import BaseDialog, GridParameters
from nexpy.gui.utils import report_error
from nxpeaks.nxrefine import NXRefine


def show_dialog():
    try:
        dialog = ScanDialog()
        dialog.show()
    except NeXusError as error:
        report_error("Defining New Scan", error)


class ScanDialog(BaseDialog):

    def __init__(self, parent=None):
        super(ScanDialog, self).__init__(parent)

        self.scan_file = NXroot()
        self.scan_file['entry'] = NXentry()

        self.detectors = {}
        self.entries = {}

        self.setup_sample()

        self.set_layout(self.filebox('Choose Default File'),
                        self.sample.grid(header=False),
                        self.close_buttons(save=True))
        self.set_title('New Scan')

    def setup_sample(self):
        self.scan_file['entry/sample'] = NXsample()
        self.scan_file['entry/sample/name'] = 'sample'
        self.scan_file['entry/sample/label'] = 'label'
        self.scan_file['entry/sample/temperature'] = NXfield(300.0, dtype=np.float32)
        self.scan_file['entry/sample/temperature'].attrs['units'] = 'K'
        self.sample = GridParameters()
        self.sample.add('sample', self.scan_file['entry/sample/name'], 'Sample Name')
        self.sample.add('label', self.scan_file['entry/sample/label'], 'Sample Label')
        self.sample.add('scan', 'scan', 'Scan Label')
        self.sample.add('temperature', self.scan_file['entry/sample/temperature'], 'Temperature (K)')
        
    def get_parameters(self):
        entry = self.scan_file['entry']
        entry['sample/name'] = self.sample['sample'].value
        entry['sample/label'] = self.sample['label'].value
        entry['sample/temperature'] = self.sample['temperature'].value

    def copy_parameters(self):
        self.scan_file['entry/instrument'] = self.default_file['entry/instrument']
        for entry in self.default_file.entries:
            if entry != 'entry':
                self.scan_file[entry] = self.default_file[entry]
                self.scan_file[entry].makelink(self.scan_file['entry/sample'])

    def accept(self):
        default_filename = self.get_filename()
        home_directory = os.path.dirname(default_filename)
        sample_directory = os.path.join(home_directory, self.sample['sample'].value)
        label_directory = os.path.join(home_directory, self.sample['sample'].value, self.sample['label'].value)
        scan_directory = os.path.join(label_directory, self.sample['scan'].value)
        scan_name = self.sample['sample'].value+'_'+self.sample['scan'].value
        self.default_file = nxload(default_filename)
        self.positions = len(self.default_file.entries) - 1
        try: 
            os.makedirs(scan_directory)
            for position in range(1, self.positions+1):
                os.mkdir(os.path.join(scan_directory, 'f%s' % position))
        except Exception:
            pass
        self.get_parameters()
        self.copy_parameters()
        self.scan_file.save(os.path.join(label_directory, scan_name+'.nxs'))
        self.treeview.tree.load(self.scan_file.nxfilename, 'rw')
        super(ScanDialog, self).accept()
