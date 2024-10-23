# -----------------------------------------------------------------------------
# Copyright (c) 2022, Argonne National Laboratory.
#
# Distributed under the terms of an Open Source License.
#
# The full license is in the file LICENSE.pdf, distributed with this software.
# -----------------------------------------------------------------------------

from pathlib import Path

import numpy as np
from nexpy.gui.datadialogs import GridParameters, NXDialog
from nexpy.gui.utils import report_error
from nexusformat.nexus import (NeXusError, NXdata, NXgoniometer, NXlink,
                               NXroot, NXsample, nxload)
from nxrefine.nxsettings import NXSettings


def show_dialog():
    try:
        dialog = ScanDialog()
        dialog.show()
    except NeXusError as error:
        report_error("Defining New Scan", error)


class ScanDialog(NXDialog):

    def __init__(self, parent=None):
        super().__init__(parent)

        self.config_file = None
        self.positions = 1
        self.entries = {}

        self.settings = NXSettings()

        self.directory_box = self.directorybox('Choose Experiment Directory',
                                               self.choose_directory,
                                               default=False)
        self.set_layout(self.directory_box,
                        self.close_buttons(close=True))

        self.set_title('New Scan')

    @property
    def home_directory(self):
        return Path(self.get_directory())

    @property
    def configuration(self):
        return self.configuration_box.currentText()

    @property
    def sample(self):
        return Path(self.sample_box.currentText()).parent.name

    @property
    def label(self):
        return Path(self.sample_box.currentText()).name

    @property
    def position(self):
        try:
            return int(self.scan_box.currentText())
        except ValueError:
            return 1

    def choose_directory(self):
        super().choose_directory()
        self.mainwindow.default_directory = str(self.home_directory)
        self.setup_directory()
        self.insert_layout(1, self.sample_layout)
        self.activate()

    def setup_directory(self):
        self.sample_box = self.select_box(self.get_samples())
        self.sample_layout = self.make_layout(
            self.action_buttons(('Choose Sample', self.choose_sample)),
            self.sample_box)
        self.configuration_box = self.select_box(self.get_configurations())
        self.configuration_layout = self.make_layout(
            self.action_buttons(('Choose Experiment Configuration',
                                 self.choose_configuration)),
            self.configuration_box)

    def get_samples(self):
        if self.home_directory.exists():
            sample_directories = [f for f in self.home_directory.iterdir()
                                  if f.is_dir()]
        else:
            return []
        samples = []
        for sample_directory in sample_directories:
            label_directories = [f for f in sample_directory.iterdir()
                                 if f.is_dir()]
            for label_directory in label_directories:
                samples.append(
                    label_directory.relative_to(self.home_directory))
        return [str(sample) for sample in samples]

    def choose_sample(self):
        self.insert_layout(2, self.configuration_layout)

    def get_configurations(self):
        directory = self.home_directory / 'configurations'
        if directory.exists():
            return sorted([str(f.name) for f in directory.glob('*.nxs')])
        else:
            return []

    def choose_configuration(self):
        config_file = (self.home_directory / 'configurations' /
                       self.configuration)
        self.scan_box = self.select_box(['1'], slot=self.choose_position)
        self.scan_layout = self.make_layout(
            self.labels('Position', header=True), self.scan_box)
        if config_file.exists():
            self.config_file = nxload(config_file)
            self.positions = len(self.config_file.entries) - 1
            self.scan_box.clear()
            for position in range(1, self.positions+1):
                self.scan_box.addItem(f'{position}')
            self.scan_box.setCurrentIndex(0)
            self.copy_configuration()
        self.setup_scans()
        self.read_parameters()
        self.insert_layout(3, self.scan.grid(header=False))
        self.insert_layout(4, self.scan_layout)
        for p in range(1, self.positions+1):
            self.insert_layout(p+4, self.entries[p].grid_layout)
        self.insert_layout(self.positions+5,
                           self.action_buttons(('Make Scan File',
                                                self.make_scan)))

    def setup_scans(self):
        default = self.settings['nxrefine']
        self.scan = GridParameters()
        self.scan.add('scan', 'scan', 'Scan Label')
        self.scan.add('temperature', 300.0, 'Temperature (K)')
        self.scan.add('phi_start', default['phi'], 'Phi Start (deg)')
        self.scan.add('phi_end', default['phi_end'], 'Phi End (deg)')
        self.scan.add('phi_step', default['phi_step'], 'Phi Step (deg)')
        self.scan.add('frame_rate', default['frame_rate'], 'Frame Rate (Hz)')

        for position in range(1, self.positions+1):
            self.setup_position(position)

    def setup_position(self, position):
        default = self.settings['nxrefine']
        self.entries[position] = GridParameters()
        self.entries[position].add('chi', default['chi'], 'Chi (deg)')
        self.entries[position].add('omega', default['omega'], 'Omega (deg)')
        self.entries[position].add('theta', default['theta'], 'Theta (deg)')
        self.entries[position].add('x', default['x'], 'Translation - x (mm)')
        self.entries[position].add('y', default['y'], 'Translation - y (mm)')
        self.entries[position].add('linkfile', f'f{position:d}.h5',
                                   'Detector Filename')
        self.entries[position].add(
            'linkpath', '/entry/data/data', 'Detector Data Path')
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
            entry = self.scan_file[f'f{position:d}']
            if 'instrument/goniometer/chi' in entry:
                self.entries[position]['chi'].value = (
                    entry['instrument/goniometer/chi'])
            if 'instrument/goniometer/omega' in entry:
                self.entries[position]['omega'].value = (
                    entry['instrument/goniometer/omega'])
            if 'instrument/goniometer/theta' in entry:
                self.entries[position]['theta'].value = (
                    entry['instrument/goniometer/theta'])
            elif 'instrument/goniometer/goniometer_pitch' in entry:
                self.entries[position]['theta'].value = (
                    entry['instrument/goniometer/goniometer_pitch'])
            elif 'instrument/goniometer/gonpitch' in entry:
                self.entries[position]['theta'].value = (
                    entry['instrument/goniometer/gonpitch'])
            if 'instrument/detector/translation_x' in entry:
                self.entries[position]['x'].value = (
                    entry['instrument/detector/translation_x'])
            if 'instrument/detector/translation_y' in entry:
                self.entries[position]['y'].value = (
                    entry['instrument/detector/translation_y'])

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
            entry = self.scan_file[f'f{position:d}']
            entry.makelink(self.scan_file['entry/sample'])
            phi_start = self.scan['phi_start'].value
            phi_end = self.scan['phi_end'].value
            phi_step = self.scan['phi_step'].value
            chi = self.entries[position]['chi'].value
            omega = self.entries[position]['omega'].value
            theta = self.entries[position]['theta'].value
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
            entry['instrument/goniometer/theta'] = theta
            entry['instrument/goniometer/theta_set'] = theta
            if frame_rate > 0.0:
                entry['instrument/detector/frame_time'] = 1.0 / frame_rate
            linkpath = self.entries[position]['linkpath'].value
            linkfile = Path(scan) / self.entries[position]['linkfile'].value
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
        self.mainwindow.default_directory = str(self.home_directory)
        label_directory = self.home_directory / self.sample / self.label
        scan_directory = label_directory / str(self.scan['scan'].value)
        scan_name = self.sample + '_' + self.scan['scan'].value + '.nxs'
        scan_directory.mkdir(exist_ok=True)
        self.copy_configuration()
        self.get_parameters()
        self.scan_file.save(label_directory / scan_name)
        self.treeview.tree.load(self.scan_file.nxfilename, 'r')
