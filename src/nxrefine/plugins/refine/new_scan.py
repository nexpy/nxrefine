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
        self.configuration_box = self.select_configuration()
        self.configuration_layout = self.make_layout(
            self.action_buttons(('Choose Experiment Configuration', 
                                 self.choose_configuration)),
            self.configuration_box)
        self.sample_box = self.select_sample()
        self.sample_layout = self.make_layout(
            self.action_buttons(('Choose Sample', self.choose_sample)),
            self.sample_box)
        self.scan_box = self.select_box(['1'], slot=self.choose_position)
        self.setup_scans()

        self.set_layout(self.directory_box,
                        self.configuration_layout,
                        self.sample_layout,
                        self.scan.grid(header=False),
                        self.make_layout(self.labels('Position'), self.scan_box),
                        self.entries[1].grid(header=False),
                        self.entries[2].grid(header=False),
                        self.entries[3].grid(header=False),
                        self.entries[4].grid(header=False),
                        self.entries[5].grid(header=False),
                        self.action_buttons(('Make Scan File', self.make_scan)),
                        self.close_buttons(close=True))

        for i in self.entries:
            self.entries[i].hide_grid()
        self.entries[1].show_grid()
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

    def setup_directory(self):
        self.configuration_box.clear()
        configurations = self.get_configurations()
        for configuration in configurations:
            self.configuration_box.addItem(configuration)
        self.choose_configuration()
        self.sample_box.clear()
        samples = self.get_samples()
        for sample in samples:
            self.sample_box.addItem(sample)
        self.sample_box.adjustSize()
        self.choose_sample()

    def select_configuration(self):
        return self.select_box(self.get_configurations())

    def get_configurations(self):
        home_directory = self.get_directory()
        if (os.path.exists(home_directory) and 
            'configurations' in os.listdir(home_directory)):
            return [f for f in 
                    os.listdir(os.path.join(home_directory, 'configurations'))
                    if f.endswith('.nxs')]
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
        pass
                
    def setup_scans(self):
        self.scan = GridParameters()
        self.scan.add('scan', 'scan', 'Scan Label')
        self.scan.add('temperature', 300.0, 'Temperature (K)')
        self.scan.add('phi_start', -5.0, 'Phi Start (deg)')
        self.scan.add('phi_end', 360.0, 'Phi End (deg)')
        self.scan.add('phi_step', 0.1, 'Phi Step (deg)')
        self.scan.add('frame_rate', 10, 'Frame Rate (Hz)')
        
        for position in range(1, 6):
            self.setup_position(position)

    def setup_position(self, position):
        self.entries[position] = GridParameters()
        self.entries[position].add('chi', 0.0, 'Chi')
        self.entries[position].add('gonpitch', 0.0, 'Goniometer Pitch')
        self.entries[position].add('linkfile', 'f%d.h5' % position, 'Detector Filename')
        self.entries[position].add('linkpath', '/entry/data/data', 'Detector Data Path')

    def choose_position(self):
        for i in self.entries:
            self.entries[i].hide_grid()
        if self.position in self.entries:
            self.entries[self.position].show_grid()

    def copy_configuration(self):
        self.scan_file = NXroot()
        for entry in self.config_file.entries:
            self.scan_file[entry] = self.config_file[entry]
        self.read_parameters()

    def read_parameters(self):
        for position in range(1, self.positions+1):
            entry = self.scan_file['f%d' % position]
            self.entries[position]['chi'].value = entry['instrument/goniometer/chi']
            self.entries[position]['gonpitch'].value = entry['instrument/goniometer/goniometer_pitch']

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
            gonpitch = self.entries[position]['gonpitch'].value
            frame_rate = self.scan['frame_rate'].value
            if 'goniometer' not in entry['instrument']:
                entry['instrument/goniometer'] = NXgoniometer()
            entry['instrument/goniometer/phi'] = phi_start
            entry['instrument/goniometer/phi_set'] = phi_start
            entry['instrument/goniometer/phi'].attrs['step'] = phi_step
            entry['instrument/goniometer/phi'].attrs['end'] = phi_end
            entry['instrument/goniometer/chi'] = chi
            entry['instrument/goniometer/chi_set'] = chi
            entry['instrument/goniometer/goniometer_pitch'] = gonpitch
            entry['instrument/goniometer/goniometer_pitch_set'] = gonpitch
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
        scan_directory = os.path.join(label_directory, self.scan['scan'].value)
        scan_name = self.sample+'_'+self.scan['scan'].value
        try: 
            os.makedirs(scan_directory)
        except Exception:
            pass
        self.copy_configuration()
        self.get_parameters()
        self.scan_file.save(os.path.join(label_directory, scan_name+'.nxs'))
        self.treeview.tree.load(self.scan_file.nxfilename, 'r')
