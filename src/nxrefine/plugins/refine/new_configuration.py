import os

import numpy as np
from nexpy.gui.datadialogs import GridParameters, NXDialog
from nexpy.gui.utils import report_error
from nexpy.gui.widgets import NXLabel
from nexusformat.nexus import (NXdetector, NXentry, NXfield, NXgoniometer,
                               NXinstrument, NXmonochromator, NXparameters,
                               NXroot)
from pyFAI.detectors import ALL_DETECTORS


def show_dialog():
        dialog = ConfigurationDialog()
        dialog.show()


class ConfigurationDialog(NXDialog):

    def __init__(self, parent=None):
        super(ConfigurationDialog, self).__init__(parent)

        self.configuration_file = NXroot()
        self.configuration_file['entry'] = NXentry()

        self.detectors = {}
        self.entries = {}

        self.setup_groups()
        self.setup_configuration()
        self.setup_analysis()
        self.setup_scan()
        self.setup_instrument()

        self.set_layout(self.directorybox('Choose Experiment Directory', 
                                          default=False),
                        self.configuration.grid(header=False),
                        self.analysis.grid(header=False, 
                                           title='Analysis Settings'),
                        self.scan.grid(header=False, title='Scan Settings'),
                        self.instrument.grid(header=False, 
                                             title='Detector Settings'))
        self.set_title('New Configuration')

    def setup_groups(self):
        entry = self.configuration_file['entry']
        entry['nxreduce'] = NXparameters()
        entry['instrument'] = NXinstrument()
        entry['instrument/monochromator'] = NXmonochromator()
        entry['instrument/goniometer'] = NXgoniometer()
        entry['instrument/detector'] = NXdetector()    

    def setup_configuration(self):
        entry = self.configuration_file['entry']
        entry['instrument/monochromator/wavelength'] = NXfield(0.5, dtype=np.float32)
        entry['instrument/monochromator/wavelength'].attrs['units'] = 'Angstroms'
        entry['instrument/monochromator/energy'] = NXfield(12.398419739640717/0.5, dtype=np.float32)
        entry['instrument/monochromator/energy'].attrs['units'] = 'keV'
        entry['instrument/goniometer'] = NXgoniometer()
        entry['instrument/detector'] = NXdetector()
        self.configuration = GridParameters()
        self.configuration.add('configuration', 'configuration', 
                               'Configuration Filename')
        self.configuration.add('wavelength', 
                               entry['instrument/monochromator/wavelength'], 
                               'Wavelength (Å)')

    def setup_analysis(self):
        entry = self.configuration_file['entry']        
        entry['nxreduce/threshold'] = NXfield(50000.0, dtype=float)
        entry['nxreduce/monitor'] = NXfield('monitor2')
        entry['nxreduce/norm'] = NXfield(30000.0, dtype=float)
        entry['nxreduce/first_frame'] = NXfield(0, dtype=int)
        entry['nxreduce/last_frame'] = NXfield(3650, dtype=int)
        entry['nxreduce/radius'] = NXfield(0.2, dtype=float)
        self.analysis = GridParameters()
        self.analysis.add('threshold', entry['nxreduce/threshold'], 
                          'Peak Threshold')
        self.analysis.add('first', entry['nxreduce/first_frame'], 
                          'First Frame')
        self.analysis.add('last', entry['nxreduce/last_frame'], 
                          'Last Frame')
        self.analysis.add('monitor', ['monitor1', 'monitor2'], 
                          'Normalization Monitor')
        self.analysis['monitor'].value = 'monitor2'
        self.analysis.add('norm', entry['nxreduce/norm'], 
                          'Normalization Value')
        self.analysis.add('radius', entry['nxreduce/radius'], 
                          'Punch Radius (Å)')

    def setup_scan(self):
        entry = self.configuration_file['entry']
        entry['instrument/goniometer/chi'] = NXfield(-90.0, dtype=float)
        entry['instrument/goniometer/chi'].attrs['units'] = 'degree'
        entry['instrument/goniometer/phi'] = NXfield(-5.0, dtype=float)
        entry['instrument/goniometer/phi'].attrs['step'] = NXfield(0.1, 
                                                                   dtype=float)
        entry['instrument/goniometer/phi'].attrs['end'] = NXfield(360.0, 
                                                                  dtype=float)
        entry['instrument/goniometer/phi'].attrs['units'] = 'degree'
        entry['instrument/detector/frame_time'] = 0.1
        self.scan = GridParameters()
        self.scan.add('chi', -90.0, 'Chi (deg)')
        self.scan.add('phi_start', -5.0, 'Phi Start (deg)')
        self.scan.add('phi_end', 360.0, 'Phi End (deg)')
        self.scan.add('phi_step', 0.1, 'Phi Step (deg)')
        self.scan.add('frame_rate', 10, 'Frame Rate (Hz)')

    def setup_instrument(self):
        entry = self.configuration_file['entry']
        entry['instrument/detector/distance'] = NXfield(100.0, dtype=float)
        entry['instrument/detector/distance'].attrs['units'] = 'mm'
        self.instrument = GridParameters()
        self.instrument.add('distance', entry['instrument/detector/distance'], 
                            'Detector Distance (mm)')
        detector_list = sorted(list(set([detector().name 
                                    for detector in ALL_DETECTORS.values()])))
        self.instrument.add('detector', detector_list, 'Detector')
        self.instrument['detector'].value = 'Pilatus CdTe 2M'
        self.instrument.add('positions', [0,1,2,3,4,5,6,7,8], 
                            'Number of Detector Positions', 
                            slot=self.set_entries)
        self.instrument['positions'].value = '0'

    def setup_entry(self, position):
        entry = NXentry()
        self.detectors[position] = GridParameters()
        self.detectors[position].add('x', 0.0, 'Translation - x (mm)')
        self.detectors[position].add('y', 0.0, 'Translation - y (mm)')
        self.detectors[position].add('omega', 0.0, 'Omega (deg)')
        self.configuration_file['f%s' % position] = entry

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
                                          range(1,self.positions+1)], 
                                         slot=self.choose_position)
        self.entry_layout = self.make_layout(self.labels('Position', 
                                                         header=True), 
                                             self.entry_box)
        self.add_layout(self.entry_layout)
        for position in range(1,self.positions+1):
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
        entry['nxreduce/monitor'] = self.analysis['monitor'].value
        entry['nxreduce/norm'] = self.analysis['norm'].value
        entry['nxreduce/radius'] = self.analysis['radius'].value
        entry['instrument/monochromator/wavelength'] = self.configuration['wavelength'].value
        entry['instrument/monochromator/energy'] = 12.398419739640717 /  self.configuration['wavelength'].value
        detector = self.get_detector()
        entry['instrument/detector/description'] = detector.name
        entry['instrument/detector/distance'] = self.instrument['distance'].value
        entry['instrument/detector/pixel_size'] = detector.pixel1 * 1000
        entry['instrument/detector/pixel_size'].attrs['units'] = 'mm'
        entry['instrument/detector/pixel_mask'] = detector.mask
        entry['instrument/detector/shape'] = detector.shape
        entry['instrument/detector/yaw'] = 0.0
        entry['instrument/detector/pitch'] = 0.0
        entry['instrument/detector/roll'] = 0.0
        for position in range(1, self.positions+1):
            entry = self.configuration_file['f%s' % position]
            entry['instrument'] = self.configuration_file['entry/instrument']
            entry['instrument/detector/translation_x'] = self.detectors[position]['x'].value
            entry['instrument/detector/translation_x'].attrs['units'] = 'mm'
            entry['instrument/detector/translation_y'] = self.detectors[position]['y'].value
            entry['instrument/detector/translation_y'].attrs['units'] = 'mm'
            if self.scan['frame_rate'].value > 0.0:
                entry['instrument/detector/frame_time'] = 1.0 / self.scan['frame_rate'].value
            else:
                entry['instrument/detector/frame_time'] = 0.1
            entry['instrument/detector/frame_time'].attrs['units'] = 's'
            entry['instrument/goniometer/phi'] = self.scan['phi_start'].value
            entry['instrument/goniometer/phi'].attrs['step'] = self.scan['phi_step'].value
            entry['instrument/goniometer/phi'].attrs['end'] = self.scan['phi_end'].value
            entry['instrument/goniometer/chi'] = self.scan['chi'].value
            entry['instrument/goniometer/omega'] = self.detectors[position]['omega'].value

    def accept(self):
        try:
            experiment_directory = self.get_directory()
            configuration_directory = os.path.join(experiment_directory,
                                                   'configurations')
            self.mainwindow.default_directory = experiment_directory
            self.get_parameters()
            self.configuration_file.save(os.path.join(configuration_directory,
                            self.configuration['configuration'].value+'.nxs'))
            self.treeview.tree.load(self.configuration_file.nxfilename, 'rw')
            super(ConfigurationDialog, self).accept()
        except Exception as error:
            report_error("Defining New Configuration", error)
