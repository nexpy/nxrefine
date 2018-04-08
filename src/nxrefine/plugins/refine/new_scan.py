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
        self.setup_scan()

        self.set_layout(self.directorybox('Choose Data Directory'), 
                        self.filebox('Choose Experiment File'),
                        self.sample.grid(header=False),
                        self.scan.grid(header=False),
                        self.action_buttons(('Make Scan File', self.make_scan)),
                        self.close_buttons(close=True))
        self.set_title('New Scan')

    def setup_sample(self):
        self.sample = GridParameters()
        self.sample.add('sample', 'sample', 'Sample Name')
        self.sample.add('label', 'label', 'Sample Label')
        self.sample.add('scan', 'scan', 'Scan Label')
        self.sample.add('temperature', 300.0, 'Temperature (K)')

    def setup_entry(self, position):
        entry = NXentry()
        self.detectors[position] = GridParameters()
        self.detectors[position].add('x', 0.0, 'Translation - x (mm)')
        self.detectors[position].add('y', 0.0, 'Translation - y (mm)')
        self.experiment_file['f%s' % position] = entry

    def setup_scan(self):
        self.scan = GridParameters()
        self.scan.add('phi_start', -5.0, 'Phi Start')
        self.scan.add('phi_end', 360.0, 'Phi End')
        self.scan.add('phi_step', 0.1, 'Phi Step')
        self.scan.add('chi', -90.0, 'Chi')
        self.scan.add('omega', 0.0, 'Omega')
        self.scan.add('frame_rate', 10.0, 'Frame Rate (Hz)')

    def copy_experiment(self, experiment):
        self.scan_file = NXroot()
        for entry in experiment.entries:
            self.scan_file[entry] = experiment[entry]

    def get_parameters(self):
        for e in self.scan_file.entries:
            entry = self.scan_file[e]
            if e == 'entry':
                entry['sample'] = NXsample()
                entry['sample/name'] = self.sample['sample'].value
                entry['sample/label'] = self.sample['label'].value
                entry['sample/temperature'] = self.sample['temperature'].value
                entry['sample/temperature'].attrs['units'] = 'K'
            else:
                entry.makelink(self.scan_file['entry/sample'])
                phi_start = self.scan['phi_start'].value
                phi_end = self.scan['phi_end'].value
                phi_step = self.scan['phi_step'].value
                chi = self.scan['chi'].value
                omega = self.scan['omega'].value
                frame_rate = self.scan['frame_rate'].value
                if 'goniometer' not in entry['instrument']:
                    entry['instrument/goniometer'] = NXgoniometer()
                entry['instrument/goniometer/phi'] = [phi_start, phi_start+phi_step]
                entry['instrument/goniometer/chi'] = chi
                entry['instrument/goniometer/omega'] = omega
                entry['data'] = NXdata()
                scan = self.sample['scan'].value
                entry['data'].nxsignal = NXlink('/entry/data/data', 
                    file=os.path.join(scan, entry.nxname+'.h5'))
                entry['data/x_pixel'] = np.arange(1475, dtype=np.int32)
                entry['data/y_pixel'] = np.arange(1679, dtype=np.int32)
                entry['data/frame_number'] = np.arange(3649, dtype=np.int32)
                entry['data'].nxaxes = [entry['data/frame_number'],
                                        entry['data/y_pixel'],
                                        entry['data/x_pixel']]

    def make_scan(self):
        home_directory = self.get_directory()
        experiment_template = nxload(self.get_filename())
        self.copy_experiment(experiment_template)
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
