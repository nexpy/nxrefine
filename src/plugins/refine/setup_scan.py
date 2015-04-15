import os
import numpy as np
from nexusformat.nexus import *
from nexpy.gui.datadialogs import BaseDialog, GridParameters
from nexpy.gui.mainwindow import report_error
from nxpeaks.nxrefine import NXRefine


def show_dialog(parent=None):
    dialog = ScanDialog(parent)
    dialog.show()


class ScanDialog(BaseDialog):

    def __init__(self, parent=None):
        super(ScanDialog, self).__init__(parent)

        self.scan_file = NXroot()
        self.scan_file['entry'] = NXentry()

        self.detectors = {}
        self.entries = {}

        self.setup_sample()
        self.setup_instrument()

        self.set_layout(self.directorybox('Choose Home Directory'), 
                        self.sample.grid(header=False), 
                        self.instrument.grid(header=False))
        self.set_title('Setup Scan')

    def setup_sample(self):
        self.scan_file['entry/sample'] = NXsample()
        self.scan_file['entry/sample/name'] = 'sample'
        self.scan_file['entry/sample/label'] = 'label'
        self.scan_file['entry/sample/temperature'] = NXfield(300.0, dtype=np.float32)
        self.scan_file['entry/sample/temperature'].attrs['units'] = 'K'
        self.scan_file['entry/sample/lattice_centring'] = NXRefine.centrings[0]
        self.scan_file['entry/sample/unit_cell_group'] = NXRefine.symmetries[0]
        self.scan_file['entry/sample/unitcell_a'] = NXfield(3.0, dtype=np.float32)
        self.scan_file['entry/sample/unitcell_b'] = NXfield(3.0, dtype=np.float32)
        self.scan_file['entry/sample/unitcell_c'] = NXfield(3.0, dtype=np.float32)
        self.scan_file['entry/sample/unitcell_alpha'] = NXfield(90.0, dtype=np.float32)
        self.scan_file['entry/sample/unitcell_beta'] = NXfield(90.0, dtype=np.float32)
        self.scan_file['entry/sample/unitcell_gamma'] = NXfield(90.0, dtype=np.float32)
        self.sample = GridParameters()
        self.sample.add('sample', self.scan_file['entry/sample/name'], 'Sample Name')
        self.sample.add('label', self.scan_file['entry/sample/label'], 'Sample Label')
        self.sample.add('scan', 'scan', 'Scan Label')
        self.sample.add('temperature', self.scan_file['entry/sample/temperature'], 'Temperature (K)')
        self.sample.add('centring', NXRefine.centrings, 'Cell Centring')
        self.sample.add('symmetry', NXRefine.symmetries, 'Symmetry')
        self.sample.add('a', self.scan_file['entry/sample/unitcell_a'], 'Unit Cell - a (Ang)')
        self.sample.add('b', self.scan_file['entry/sample/unitcell_b'], 'Unit Cell - b (Ang)')
        self.sample.add('c', self.scan_file['entry/sample/unitcell_c'], 'Unit Cell - c (Ang)')
        self.sample.add('alpha', self.scan_file['entry/sample/unitcell_alpha'], 'Unit Cell - alpha (deg)')
        self.sample.add('beta', self.scan_file['entry/sample/unitcell_beta'], 'Unit Cell - beta (deg)')
        self.sample.add('gamma', self.scan_file['entry/sample/unitcell_gamma'], 'Unit Cell - gamma (deg)')

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
        entry = self.scan_file['s%s' % (position+1)] = NXentry()
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
        entry['sample/lattice_centring'] = self.sample['centring'].value
        entry['sample/unit_cell_group'] = self.sample['symmetry'].value
        entry['sample/unitcell_a'] = self.sample['a'].value
        entry['sample/unitcell_b'] = self.sample['b'].value
        entry['sample/unitcell_c'] = self.sample['c'].value
        entry['sample/unitcell_alpha'] = self.sample['alpha'].value
        entry['sample/unitcell_beta'] = self.sample['beta'].value
        entry['sample/unitcell_gamma'] = self.sample['gamma'].value
        entry['instrument/monochromator/wavelength'] = self.instrument['wavelength'].value
        entry['instrument/detector/distance'] = self.instrument['distance'].value
        entry['instrument/detector/pixel_size'] = self.instrument['pixel'].value
        for position in range(self.positions):
            entry = self.scan_file['s%s' % (position+1)]
            entry['instrument/monochromator/wavelength'] = self.instrument['wavelength'].value
            entry['instrument/detector/distance'] = self.instrument['distance'].value
            entry['instrument/detector/pixel_size'] = self.instrument['pixel'].value
            entry['instrument/detector/beam_center_x'] = self.detectors[position]['xc'].value
            entry['instrument/detector/beam_center_y'] = self.detectors[position]['yc'].value
            entry.makelink(self.scan_file['entry/sample'])

    def accept(self):
        home_directory = self.get_directory()
        sample_directory = os.path.join(home_directory, self.sample['name'].value)
        label_directory = os.path.join(sample_directory, self.sample['label'].value)
        scan_directory = os.path.join(label_directory, self.sample['scan'].value)
        scan_name = self.sample['name']+self.sample['scan']+'.nxs'
        if not os.path.exists(sample_directory):
            os.mkdir(sample_directory)
        if not os.path.exists(label_directory):
            os.mkdir(label_directory)        
        if not os.path.exists(scan_directory):
            os.mkdir(scan_directory)
        self.scan_file.save(os.path.join(label_directory, scan_name))
        
        
        
        
        