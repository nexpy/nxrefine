from __future__ import unicode_literals
import os
import numpy as np
from nexusformat.nexus import *
from nexpy.gui.datadialogs import BaseDialog, GridParameters
from nexpy.gui.utils import report_error
from nxrefine.nxrefine import NXRefine


def show_dialog():
    try:
        dialog = ScanDialog()
        dialog.show()
    except Exception as error:
        report_error("Defining New Scan", error)


class ScanDialog(BaseDialog):

    def __init__(self, parent=None):
        super(ScanDialog, self).__init__(parent)

        self.scan_file = NXroot()
        self.scan_file['entry'] = NXentry()

        self.detectors = {}
        self.entries = {}

        self.setup_sample()
        self.setup_instrument()

        self.set_layout(self.directorybox('Choose Data Directory'), 
                        self.sample.grid(header=False), 
                        self.instrument.grid(header=False))
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

    def setup_instrument(self):
        entry = self.scan_file['entry']
        entry.instrument = NXinstrument()
        entry.instrument.monochromator = NXmonochromator()
        entry.instrument.detector = NXdetector()
        entry['instrument/monochromator/wavelength'] = NXfield(0.5, dtype=np.float32)
        entry['instrument/monochromator/wavelength'].attrs['units'] = 'Angstroms'
        entry['instrument/detector/distance'] = NXfield(100.0, dtype=np.float32)
        entry['instrument/detector/distance'].attrs['units'] = 'mm'
        entry['instrument/detector/pixel_size'] = NXfield(0.172, dtype=np.float32)
        entry['instrument/detector/pixel_size'].attrs['units'] = 'mm'
        self.instrument = GridParameters()
        self.instrument.add('wavelength', entry['instrument/monochromator/wavelength'], 'Wavelength (Ang)')
        self.instrument.add('distance', entry['instrument/detector/distance'], 'Detector Distance (mm)')
        self.instrument.add('pixel', entry['instrument/detector/pixel_size'], 'Pixel Size (mm)')
        self.instrument.add('positions', [0,1,2,3,4], 'Number of Detector Positions', slot=self.set_entries)
        self.instrument['positions'].value = '0'

    def setup_entry(self, position):
        entry = self.scan_file['f%s' % position] = NXentry()
        entry.instrument = NXinstrument()
        entry.instrument.detector = NXdetector()
        entry.instrument.monochromator = NXmonochromator()
        entry['instrument/detector/beam_center_x'] = NXfield(1024.0, dtype=np.float32)
        entry['instrument/detector/beam_center_y'] = NXfield(1024.0, dtype=np.float32)
        self.detectors[position] = GridParameters()
        self.detectors[position].add('xc', entry['instrument/detector/beam_center_x'], 'Beam Center - x')
        self.detectors[position].add('yc', entry['instrument/detector/beam_center_y'], 'Beam Center - y')

    @property
    def positions(self):
        return int(self.instrument['positions'].value)
 
    def set_entries(self):
        for position in range(1,self.positions+1):
            self.setup_entry(position)
            self.layout.addLayout(self.detectors[position].grid(header=False, title='Position %s'%position))
        self.layout.addWidget(self.close_buttons(save=True))

    def get_parameters(self):
        entry = self.scan_file['entry']
        entry['sample/name'] = self.sample['sample'].value
        entry['sample/label'] = self.sample['label'].value
        entry['sample/temperature'] = self.sample['temperature'].value
        entry['instrument/monochromator/wavelength'] = self.instrument['wavelength'].value
        entry['instrument/detector/distance'] = self.instrument['distance'].value
        entry['instrument/detector/pixel_size'] = self.instrument['pixel'].value
        for position in range(1, self.positions+1):
            entry = self.scan_file['f%s' % position]
            entry['instrument/monochromator/wavelength'] = self.instrument['wavelength'].value
            entry['instrument/detector/distance'] = self.instrument['distance'].value
            entry['instrument/detector/pixel_size'] = self.instrument['pixel'].value
            entry['instrument/detector/beam_center_x'] = self.detectors[position]['xc'].value
            entry['instrument/detector/beam_center_y'] = self.detectors[position]['yc'].value
            entry.makelink(self.scan_file['entry/sample'])

    def accept(self):
        home_directory = self.get_directory()
        sample_directory = os.path.join(home_directory, self.sample['sample'].value)
        label_directory = os.path.join(home_directory, self.sample['sample'].value, self.sample['label'].value)
        scan_directory = os.path.join(label_directory, self.sample['scan'].value)
        scan_name = self.sample['sample'].value+'_'+self.sample['scan'].value
        try: 
            os.makedirs(scan_directory)
            for position in range(1, self.positions+1):
                os.mkdir(os.path.join(scan_directory, 'f%s' % position))
        except Exception:
            pass
        self.get_parameters()
        self.scan_file.save(os.path.join(label_directory, scan_name+'.nxs'))
        self.treeview.tree.load(self.scan_file.nxfilename, 'rw')
        super(ScanDialog, self).accept()
