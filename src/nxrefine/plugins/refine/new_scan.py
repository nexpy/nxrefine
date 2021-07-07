from __future__ import unicode_literals
import os
import numpy as np
from nexusformat.nexus import *
from nexpy.gui.datadialogs import NXDialog, GridParameters
from nexpy.gui.utils import report_error


def show_dialog():
    try:
        dialog = ScanDialog()
        dialog.show()
    except NeXusError as error:
        report_error("Defining New Scan", error)


class ScanDialog(NXDialog):

    def __init__(self, parent=None):
        super(ScanDialog, self).__init__(parent)

        self.config_file = None
        self.positions = 1
        self.entries = {}

        self.directory_box = self.directorybox('Choose Experiment Directory',
                                               self.choose_directory,
                                               default=False)
        self.sample_box = self.select_sample()
        self.sample_layout = self.make_layout(
            self.action_buttons(('Choose Sample', self.choose_sample)),
            self.sample_box)
        self.configuration_box = self.select_configuration()
        self.configuration_layout = self.make_layout(
            self.action_buttons(('Choose Experiment Configuration', 
                                 self.choose_configuration)),
            self.configuration_box)
        self.scan_box = self.select_box(['1'], slot=self.choose_position)
        self.scan_layout = self.make_layout(self.labels('Position'), 
                                            self.scan_box)
        self.set_layout(self.directory_box,
                        self.close_buttons(close=True))

        self.set_title('New Scan')

    @property
    def configuration(self):
        return self.configuration_box.currentText()

    @property
    def sample(self):
        return self.sample_box.currentText().split('/')[0]

    @property
    def label(self):
        return self.sample_box.currentText().split('/')[1]

    @property
    def position(self):
        try:
            return int(self.scan_box.currentText())
        except ValueError:
            return 1

    def choose_directory(self):
        super(ScanDialog, self).choose_directory()
        self.mainwindow.default_directory = self.get_directory()
        self.setup_directory()
        self.layout.insertLayout(1, self.sample_layout)

    def setup_directory(self):
        self.sample_box.clear()
        samples = self.get_samples()
        for sample in samples:
            self.sample_box.addItem(sample)
        self.sample_box.adjustSize()
        configurations = self.get_configurations()
        self.configuration_box.clear()
        for configuration in configurations:
            self.configuration_box.addItem(configuration)

    def select_sample(self):
        return self.select_box(self.get_samples())
        
    def get_samples(self):
        home_directory = self.get_directory()
        if (os.path.exists(home_directory) and 
            'configurations' in os.listdir(home_directory)):
            sample_directories = [f for f in os.listdir(home_directory)
                                  if (not f.startswith('.') and
                                      os.path.isdir(
                                        os.path.join(home_directory, f)))]
        else:
            return []
        samples = []
        for sample_directory in sample_directories:
            label_directories = [f for f in 
                os.listdir(os.path.join(home_directory, sample_directory))
                if os.path.isdir(os.path.join(home_directory, sample_directory, f))]
            for label_directory in label_directories:
                samples.append(os.path.join(sample_directory, label_directory))
        return [sample.strip() for sample in samples]
                        
    def choose_sample(self):
        self.layout.insertLayout(2, self.configuration_layout)
                
    def select_configuration(self):
        return self.select_box(self.get_configurations())

    def get_configurations(self):
        home_directory = self.get_directory()
        if (os.path.exists(home_directory) and 
            'configurations' in os.listdir(home_directory)):
            return sorted([f for f in 
                    os.listdir(os.path.join(home_directory, 'configurations'))
                    if f.endswith('.nxs')])
        else:
            return []

    def choose_configuration(self):
        home_directory = self.get_directory()
        config_file = os.path.join(home_directory, 'configurations',
                                   self.configuration)
        if os.path.exists(config_file):
            self.config_file = nxload(config_file)
            self.positions = len(self.config_file.entries) - 1
            self.scan_box.clear()
            for position in range(1, self.positions+1):
                self.scan_box.addItem('%d' % position)
            self.scan_box.setCurrentIndex(0)
            self.copy_configuration()
        self.setup_scans()
        self.read_parameters()
        self.layout.insertLayout(3, self.scan.grid(header=False))
        self.layout.insertLayout(4, self.scan_layout)
        for p in range(1, self.positions+1):
            self.layout.insertLayout(p+4, self.entries[p].grid_layout)
        self.layout.insertLayout(self.positions+5, 
                                 self.action_buttons(('Make Scan File', 
                                                      self.make_scan)))

    def setup_scans(self):
        self.scan = GridParameters()
        self.scan.add('scan', 'scan', 'Scan Label')
        self.scan.add('temperature', 300.0, 'Temperature (K)')
        self.scan.add('phi_start', -5.0, 'Phi Start (deg)')
        self.scan.add('phi_end', 360.0, 'Phi End (deg)')
        self.scan.add('phi_step', 0.1, 'Phi Step (deg)')
        self.scan.add('frame_rate', 10, 'Frame Rate (Hz)')
        
        for position in range(1, self.positions+1):
            self.setup_position(position)

    def setup_position(self, position):
        self.entries[position] = GridParameters()
        self.entries[position].add('chi', -90.0, 'Chi (deg)')
        self.entries[position].add('omega', 0.0, 'Omega (deg)')
        self.entries[position].add('x', 0.0, 'Translation - x (mm)')
        self.entries[position].add('y', 0.0, 'Translation - y (mm)')
        self.entries[position].add('linkfile', 'f%d.h5' % position, 'Detector Filename')
        self.entries[position].add('linkpath', '/entry/data/data', 'Detector Data Path')
        self.entries[position].grid(header=False)
        if position != 1:
            self.entries[position].hide_grid()

    def choose_position(self):
        for i in self.entries:
            self.entries[i].hide_grid()
        if self.position in self.entries:
            self.entries[self.position].show_grid()

    def copy_configuration(self):
        self.scan_file = NXroot()
        for entry in self.config_file.entries:
            self.scan_file[entry] = self.config_file[entry]

    def read_parameters(self):
        for position in range(1, self.positions+1):
            entry = self.scan_file['f%d' % position]
            self.entries[position]['chi'].value = entry['instrument/goniometer/chi']
            self.entries[position]['omega'].value = entry['instrument/goniometer/omega']
            self.entries[position]['x'].value = entry['instrument/detector/translation_x']
            self.entries[position]['y'].value = entry['instrument/detector/translation_y']

    def get_parameters(self):
        entry = self.scan_file['entry']
        if 'sample' not in entry:
            entry['sample'] = NXsample()
        entry['sample/name'] = self.sample
        entry['sample/label'] = self.label
        entry['sample/temperature'] = self.scan['temperature'].value
        entry['sample/temperature'].attrs['units'] = 'K'
        y_size, x_size = entry['instrument/detector/shape'].nxvalue
        scan = self.scan['scan'].value
        for position in range(1, self.positions+1):
            entry = self.scan_file['f%d' % position]
            entry.makelink(self.scan_file['entry/sample'])
            phi_start = self.scan['phi_start'].value
            phi_end = self.scan['phi_end'].value
            phi_step = self.scan['phi_step'].value
            chi = self.entries[position]['chi'].value
            omega = self.entries[position]['omega'].value
            frame_rate = self.scan['frame_rate'].value
            if 'goniometer' not in entry['instrument']:
                entry['instrument/goniometer'] = NXgoniometer()
            entry['instrument/goniometer/phi'] = phi_start
            entry['instrument/goniometer/phi_set'] = phi_start
            entry['instrument/goniometer/phi'].attrs['step'] = phi_step
            entry['instrument/goniometer/phi'].attrs['end'] = phi_end
            entry['instrument/goniometer/chi'] = chi
            entry['instrument/goniometer/chi_set'] = chi
            entry['instrument/goniometer/omega'] = omega
            entry['instrument/goniometer/omega_set'] = omega
            if frame_rate > 0.0:
                entry['instrument/detector/frame_time'] = 1.0 / frame_rate
            linkpath = self.entries[position]['linkpath'].value
            linkfile = os.path.join(scan, self.entries[position]['linkfile'].value)
            entry['data'] = NXdata()
            entry['data'].nxsignal = NXlink(linkpath, linkfile) 
            entry['data/x_pixel'] = np.arange(x_size, dtype=np.int32)
            entry['data/y_pixel'] = np.arange(y_size, dtype=np.int32)
            entry['data/frame_number'] = np.arange(
                (phi_end-phi_start)/phi_step, dtype=np.int32)
            entry['data'].nxaxes = [entry['data/frame_number'],
                                    entry['data/y_pixel'],
                                    entry['data/x_pixel']]

    def make_scan(self):
        home_directory = self.get_directory()
        self.mainwindow.default_directory = home_directory
        sample_directory = os.path.join(home_directory, self.sample)
        label_directory = os.path.join(home_directory, self.sample, self.label)
        scan_directory = os.path.join(label_directory, str(self.scan['scan'].value))
        scan_name = self.sample+'_'+self.scan['scan'].value
        try: 
            os.makedirs(scan_directory)
        except Exception:
            pass
        self.copy_configuration()
        self.get_parameters()
        self.scan_file.save(os.path.join(label_directory, scan_name+'.nxs'))
        self.treeview.tree.load(self.scan_file.nxfilename, 'r')
