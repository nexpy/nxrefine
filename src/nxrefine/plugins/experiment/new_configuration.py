# -----------------------------------------------------------------------------
# Copyright (c) 2015-2021, NeXpy Development Team.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file COPYING, distributed with this software.
# -----------------------------------------------------------------------------

import os

import numpy as np
from nexpy.gui.datadialogs import GridParameters, NXDialog
from nexpy.gui.utils import report_error
from nexusformat.nexus import (NXdetector, NXentry, NXfield, NXgoniometer,
                               NXinstrument, NXmonochromator, NXparameters,
                               NXsource, NXroot)
from nxrefine.nxsettings import NXSettings
from pyFAI.detectors import ALL_DETECTORS


def show_dialog():
    dialog = ConfigurationDialog()
    dialog.show()


class ConfigurationDialog(NXDialog):

    def __init__(self, parent=None):
        super().__init__(parent)

        self.configuration_file = NXroot()
        self.configuration_file['entry'] = NXentry()

        self.detectors = {}
        self.entries = {}

        self.set_layout(self.directorybox('Choose Experiment Directory',
                                          default=False))
        self.set_title('New Configuration')

    def choose_directory(self):
        super().choose_directory()
        self.settings = NXSettings(self.get_directory()).settings

        self.setup_groups()
        self.setup_configuration()
        self.setup_analysis()
        self.setup_scan()
        self.setup_instrument()

        self.add_layout(self.configuration.grid(header=False))
        self.add_layout(self.analysis.grid(header=False,
                                           title='Analysis Settings'))
        self.add_layout(self.scan.grid(header=False, title='Scan Settings'))
        self.add_layout(self.instrument.grid(header=False,
                                             title='Detector Settings'))

    def setup_groups(self):
        entry = self.configuration_file['entry']
        entry['nxreduce'] = NXparameters()
        entry['instrument'] = NXinstrument()
        entry['instrument/source'] = NXsource()
        entry['instrument/monochromator'] = NXmonochromator()
        entry['instrument/goniometer'] = NXgoniometer()
        entry['instrument/detector'] = NXdetector()

    def setup_configuration(self):
        default = self.settings['instrument']
        entry = self.configuration_file['entry']
        entry['instrument/name'] = default['instrument']
        entry['instrument/source/name'] = default['source']
        default = self.settings['nxrefine']
        entry['instrument/monochromator/wavelength'] = NXfield(
            default['wavelength'], dtype=np.float32)
        entry['instrument/monochromator/wavelength'].attrs['units'] = (
            'Angstroms')
        entry['instrument/monochromator/energy'] = NXfield(
            12.398419739640717 / 0.5, dtype=np.float32)
        entry['instrument/monochromator/energy'].attrs['units'] = 'keV'
        entry['instrument/goniometer'] = NXgoniometer()
        entry['instrument/detector'] = NXdetector()
        self.configuration = GridParameters()
        self.configuration.add('configuration', 'configuration',
                               'Configuration Filename')
        self.configuration.add('source', entry['instrument/source/name'],
                               'Name of Facility')
        self.configuration.add('instrument', entry['instrument/name'],
                               'Instrument Name')
        self.configuration.add('wavelength',
                               entry['instrument/monochromator/wavelength'],
                               'Wavelength (Å)')

    def setup_analysis(self):
        default = self.settings['nxreduce']
        entry = self.configuration_file['entry']
        entry['nxreduce/threshold'] = NXfield(default['threshold'],
                                              dtype=float)
        entry['nxreduce/polar_max'] = NXfield(default['polar_max'],
                                              dtype=float)
        entry['nxreduce/hkl_tolerance'] = NXfield(default['hkl_tolerance'],
                                                  dtype=float)
        entry['nxreduce/monitor'] = NXfield(default['monitor'])
        entry['nxreduce/norm'] = NXfield(default['norm'], dtype=float)
        entry['nxreduce/first_frame'] = NXfield(default['first'], dtype=int)
        entry['nxreduce/last_frame'] = NXfield(default['last'], dtype=int)
        entry['nxreduce/radius'] = NXfield(default['radius'], dtype=float)
        self.analysis = GridParameters()
        self.analysis.add('threshold', entry['nxreduce/threshold'],
                          'Peak Threshold')
        self.analysis.add('first', entry['nxreduce/first_frame'],
                          'First Frame')
        self.analysis.add('last', entry['nxreduce/last_frame'],
                          'Last Frame')
        self.analysis.add('polar_max', entry['nxreduce/polar_max'],
                          'Maximum Polar Angle')
        self.analysis.add('hkl_tolerance', entry['nxreduce/hkl_tolerance'],
                          'HKL Tolerance (Å-1)')
        self.analysis.add('monitor', ['monitor1', 'monitor2'],
                          'Normalization Monitor')
        self.analysis['monitor'].value = default['monitor']
        self.analysis.add('norm', entry['nxreduce/norm'],
                          'Normalization Value')
        self.analysis.add('radius', entry['nxreduce/radius'],
                          'Punch Radius (Å)')

    def setup_scan(self):
        default = self.settings['nxrefine']
        entry = self.configuration_file['entry']
        entry['instrument/goniometer/geometry'] = 'default'
        entry['instrument/goniometer/chi'] = (
            NXfield(default['chi'], dtype=float))
        entry['instrument/goniometer/chi'].attrs['units'] = 'degree'
        entry['instrument/goniometer/phi'] = (
            NXfield(default['phi'], dtype=float))
        entry['instrument/goniometer/phi'].attrs['step'] = (
            NXfield(default['phi_step'], dtype=float))
        entry['instrument/goniometer/phi'].attrs['end'] = (
            NXfield(default['phi_end'], dtype=float))
        entry['instrument/goniometer/phi'].attrs['units'] = 'degree'
        entry['instrument/detector/frame_time'] = (
            NXfield(1/float(default['frame_rate']), dtype=float))
        self.scan = GridParameters()
        self.scan.add('phi_start', default['phi'], 'Phi Start (deg)')
        self.scan.add('phi_end', default['phi_end'], 'Phi End (deg)')
        self.scan.add('phi_step', default['phi_step'], 'Phi Step (deg)')
        self.scan.add('frame_rate', default['frame_rate'], 'Frame Rate (Hz)')

    def setup_instrument(self):
        default = self.settings['nxrefine']
        entry = self.configuration_file['entry']
        entry['instrument/detector/distance'] = NXfield(default['distance'],
                                                        dtype=float)
        entry['instrument/detector/distance'].attrs['units'] = 'mm'
        self.instrument = GridParameters()
        self.instrument.add('distance', entry['instrument/detector/distance'],
                            'Detector Distance (mm)')
        detector_list = sorted(list(set([detector().name
                                    for detector in ALL_DETECTORS.values()])))
        self.instrument.add('detector', detector_list, 'Detector')
        self.instrument['detector'].value = 'Pilatus CdTe 2M'
        self.instrument.add('positions', [0, 1, 2, 3, 4, 5, 6, 7, 8],
                            'Number of Detector Positions',
                            slot=self.set_entries)
        self.instrument['positions'].value = '0'

    def setup_entry(self, position):
        default = self.settings['nxrefine']
        entry = NXentry()
        self.detectors[position] = GridParameters()
        self.detectors[position].add('chi', default['chi'], 'Chi (deg)')
        self.detectors[position].add('omega', default['omega'], 'Omega (deg)')
        self.detectors[position].add('theta', default['theta'], 'Theta (deg)')
        self.detectors[position].add('x', default['x'], 'Translation - x (mm)')
        self.detectors[position].add('y', default['y'], 'Translation - y (mm)')
        self.configuration_file[f'f{position}'] = entry

    def get_detector(self):
        for detector in ALL_DETECTORS:
            if (ALL_DETECTORS[detector]().name
                    == self.instrument['detector'].value):
                return ALL_DETECTORS[detector]()

    @property
    def positions(self):
        return int(self.instrument['positions'].value)

    @property
    def position(self):
        try:
            return int(self.entry_box.currentText())
        except ValueError:
            return 1

    def set_entries(self):
        self.entry_box = self.select_box([str(i) for i in
                                          range(1, self.positions+1)],
                                         slot=self.choose_position)
        self.entry_layout = self.make_layout(self.labels('Position',
                                                         header=True),
                                             self.entry_box)
        self.add_layout(self.entry_layout)
        for position in range(1, self.positions+1):
            self.setup_entry(position)
            self.add_layout(self.detectors[position].grid(header=False))
            if position != 1:
                self.detectors[position].hide_grid()
        self.add_layout(self.close_buttons(save=True))

    def choose_position(self):
        for i in self.detectors:
            self.detectors[i].hide_grid()
        if self.position in self.detectors:
            self.detectors[self.position].show_grid()

    def get_parameters(self):
        entry = self.configuration_file['entry']
        entry['nxreduce/threshold'] = self.analysis['threshold'].value
        entry['nxreduce/first_frame'] = self.analysis['first'].value
        entry['nxreduce/last_frame'] = self.analysis['last'].value
        entry['nxreduce/polar_max'] = self.analysis['polar_max'].value
        entry['nxreduce/hkl_tolerance'] = self.analysis['hkl_tolerance'].value
        entry['nxreduce/monitor'] = self.analysis['monitor'].value
        entry['nxreduce/norm'] = self.analysis['norm'].value
        entry['nxreduce/radius'] = self.analysis['radius'].value
        entry['instrument/source/name'] = self.configuration['source'].value
        entry['instrument/name'] = self.configuration['instrument'].value
        entry['instrument/monochromator/wavelength'] = (
            self.configuration['wavelength'].value)
        entry['instrument/monochromator/energy'] = (
            12.398419739640717 / self.configuration['wavelength'].value)
        detector = self.get_detector()
        entry['instrument/detector/description'] = detector.name
        entry['instrument/detector/distance'] = (
            self.instrument['distance'].value)
        entry['instrument/detector/pixel_size'] = detector.pixel1 * 1000
        entry['instrument/detector/pixel_size'].attrs['units'] = 'mm'
        entry['instrument/detector/pixel_mask'] = detector.mask
        entry['instrument/detector/shape'] = detector.shape
        entry['instrument/detector/yaw'] = 0.0
        entry['instrument/detector/pitch'] = 0.0
        entry['instrument/detector/roll'] = 0.0
        for position in range(1, self.positions+1):
            entry = self.configuration_file[f'f{position}']
            entry['instrument'] = self.configuration_file['entry/instrument']
            entry['instrument/detector/translation_x'] = (
                self.detectors[position]['x'].value)
            entry['instrument/detector/translation_x'].attrs['units'] = 'mm'
            entry['instrument/detector/translation_y'] = (
                self.detectors[position]['y'].value)
            entry['instrument/detector/translation_y'].attrs['units'] = 'mm'
            if self.scan['frame_rate'].value > 0.0:
                entry['instrument/detector/frame_time'] = (
                    1.0 / self.scan['frame_rate'].value)
            else:
                entry['instrument/detector/frame_time'] = 0.1
            entry['instrument/detector/frame_time'].attrs['units'] = 's'
            entry['instrument/goniometer/phi'] = self.scan['phi_start'].value
            entry['instrument/goniometer/phi'].attrs['step'] = (
                self.scan['phi_step'].value)
            entry['instrument/goniometer/phi'].attrs['end'] = (
                self.scan['phi_end'].value)
            entry['instrument/goniometer/chi'] = (
                self.detectors[position]['chi'].value)
            entry['instrument/goniometer/omega'] = (
                self.detectors[position]['omega'].value)
            entry['instrument/goniometer/theta'] = (
                self.detectors[position]['theta'].value)

    def accept(self):
        try:
            experiment_directory = self.get_directory()
            configuration_directory = os.path.join(experiment_directory,
                                                   'configurations')
            self.mainwindow.default_directory = experiment_directory
            self.get_parameters()
            self.configuration_file.save(
                os.path.join(configuration_directory,
                             self.configuration['configuration'].value +
                             '.nxs'))
            self.treeview.tree.load(self.configuration_file.nxfilename, 'rw')
            super().accept()
        except Exception as error:
            report_error("Defining New Configuration", error)
