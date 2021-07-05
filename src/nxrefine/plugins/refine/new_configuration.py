import os
import numpy as np

from pyFAI.detectors import ALL_DETECTORS

from nexusformat.nexus import *
from nexpy.gui.datadialogs import NXDialog, GridParameters
from nexpy.gui.utils import report_error
from nexpy.gui.widgets import NXLabel


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

        self.set_layout(self.directorybox('Choose Experiment Directory', default=False),
                        self.configuration.grid(header=False),
                        NXLabel('Analysis Settings', bold=True, align='center'),
                        self.analysis.grid(header=False),
                        NXLabel('Scan Settings', bold=True, align='center'),
                        self.scan.grid(header=False),
                        NXLabel('Detector Settings', bold=True, align='center'),
                        self.instrument.grid(header=False))
        self.set_title('New Configuration')

    def setup_groups(self):
        entry = self.configuration_file['entry']
        entry['nxrefine'] = NXparameters()
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
                               'Wavelength (Ang)')

    def setup_analysis(self):
        entry = self.configuration_file['entry']        
        entry['nxrefine/threshold'] = NXfield(1000.0, dtype=np.float32)
        entry['nxrefine/monitor'] = NXfield('monitor2')
        entry['nxrefine/norm'] = NXfield(30000.0, dtype=np.float32)
        self.analysis = GridParameters()
        self.analysis.add('threshold', entry['nxrefine/threshold'], 
                          'Peak Threshold')
        self.analysis.add('monitor', ['monitor1', 'monitor2'], 
                          'Normalization Monitor')
        self.analysis['monitor'].value = 'monitor2'
        self.analysis.add('norm', entry['nxrefine/norm'], 
                          'Normalization Value')

    def setup_scan(self):
        entry = self.configuration_file['entry']
        entry['instrument/goniometer/chi'] = NXfield(-90.0, dtype=np.float32)
        entry['instrument/goniometer/chi'].attrs['units'] = 'degree'
        entry['instrument/goniometer/phi'] = NXfield(-5.0, dtype=np.float32)
        entry['instrument/goniometer/phi'].attrs['step'] = NXfield(0.1, dtype=np.float32)
        entry['instrument/goniometer/phi'].attrs['end'] = NXfield(360.0, dtype=np.float32)
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
        entry['instrument/detector/distance'] = NXfield(100.0, dtype=np.float32)
        entry['instrument/detector/distance'].attrs['units'] = 'mm'
        self.instrument = GridParameters()
        self.instrument.add('distance', entry['instrument/detector/distance'], 
                            'Detector Distance (mm)')
        detector_list = sorted(list(set([detector().name 
                                    for detector in ALL_DETECTORS.values()])))
        self.instrument.add('detector', detector_list, 'Detector')
        self.instrument['detector'].value = 'Pilatus CdTe 2M'
        self.instrument.add('positions', [0,1,2,3,4], 
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
            if ALL_DETECTORS[detector]().name == self.instrument['detector'].value:
                return ALL_DETECTORS[detector]()

    @property
    def positions(self):
        return int(self.instrument['positions'].value)
 
    def set_entries(self):
        for position in range(1,self.positions+1):
            self.setup_entry(position)
            self.layout.addLayout(self.detectors[position].grid(header=False, 
                                                title='Position %s'%position))
        self.layout.addWidget(self.close_buttons(save=True))

    def get_parameters(self):
        entry = self.configuration_file['entry']
        entry['nxrefine/threshold'] = self.analysis['threshold'].value
        entry['nxrefine/monitor'] = self.analysis['monitor'].value
        entry['nxrefine/norm'] = self.analysis['norm'].value
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
