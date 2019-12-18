import os
import numpy as np

from pyFAI.detectors import ALL_DETECTORS

from nexusformat.nexus import *
from nexpy.gui.datadialogs import NXDialog, GridParameters
from nexpy.gui.utils import report_error


def show_dialog():
    try:
        dialog = ExperimentDialog()
        dialog.show()
    except NeXusError as error:
        report_error("Defining New Experiment", error)


class ExperimentDialog(NXDialog):

    def __init__(self, parent=None):
        super(ExperimentDialog, self).__init__(parent)

        self.experiment_file = NXroot()
        self.experiment_file['entry'] = NXentry()

        self.detectors = {}
        self.entries = {}

        self.setup_instrument()

        self.set_layout(self.directorybox('Choose Experiment Directory', default=False), 
                        self.instrument.grid(header=False))
        self.set_title('New Experiment')

    def setup_instrument(self):
        entry = self.experiment_file['entry']
        entry['instrument'] = NXinstrument()
        entry['instrument/monochromator'] = NXmonochromator()
        entry['instrument/detector'] = NXdetector()
        entry['instrument/monochromator/wavelength'] = NXfield(0.5, dtype=np.float32)
        entry['instrument/monochromator/wavelength'].attrs['units'] = 'Angstroms'
        entry['instrument/monochromator/energy'] = NXfield(12.398419739640717/0.5, dtype=np.float32)
        entry['instrument/monochromator/energy'].attrs['units'] = 'keV'
        entry['instrument/detector/distance'] = NXfield(100.0, dtype=np.float32)
        entry['instrument/detector/distance'].attrs['units'] = 'mm'
        self.instrument = GridParameters()
        self.instrument.add('experiment', 'experiment', 'Experiment Name')
        self.instrument.add('wavelength', entry['instrument/monochromator/wavelength'], 'Wavelength (Ang)')
        self.instrument.add('distance', entry['instrument/detector/distance'], 'Detector Distance (mm)')
        detector_list = sorted(list(set([detector().name for detector in ALL_DETECTORS.values()])))
        self.instrument.add('detector', detector_list, 'Detector')
        self.instrument['detector'].value = 'Pilatus 6M'
        self.instrument.add('positions', [0,1,2,3,4], 'Number of Detector Positions', slot=self.set_entries)
        self.instrument['positions'].value = '0'

    def setup_entry(self, position):
        entry = NXentry()
        self.detectors[position] = GridParameters()
        self.detectors[position].add('chi', 0.0, 'Chi')
        self.detectors[position].add('gonpitch', 0.0, 'Goniometer Pitch')
        self.experiment_file['f%s' % position] = entry

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
            self.layout.addLayout(self.detectors[position].grid(header=False, title='Position %s'%position))
        self.layout.addWidget(self.close_buttons(save=True))

    def get_parameters(self):
        entry = self.experiment_file['entry']
        entry['instrument/monochromator/wavelength'] = self.instrument['wavelength'].value
        entry['instrument/monochromator/energy'] = 12.398419739640717 /  self.instrument['wavelength'].value
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
            entry = self.experiment_file['f%s' % position]
            entry['instrument'] = self.experiment_file['entry/instrument']
            entry['instrument/goniometer'] = NXgoniometer()
            entry['instrument/goniometer/chi'] = self.detectors[position]['chi'].value
            entry['instrument/goniometer/goniometer_pitch'] = self.detectors[position]['gonpitch'].value
            entry['instrument/detector/frame_time'] = 0.1
            entry['instrument/detector/frame_time'].attrs['units'] = 'seconds'

    def accept(self):
        try:
            home_directory = self.get_directory()
            self.mainwindow.default_directory = home_directory
            self.get_parameters()
            configuration_directory = os.path.join(home_directory, 'configurations')
            if not os.path.exists(configuration_directory):
                os.makedirs(configuration_directory)
            self.experiment_file.save(os.path.join(configuration_directory,
                                                   self.instrument['experiment'].value+'.nxs'))
            task_directory = os.path.join(home_directory, 'tasks')
            if not os.path.exists(task_directory):
                os.makedirs(task_directory)
            calibration_directory = os.path.join(home_directory, 'calibrations')
            if not os.path.exists(calibration_directory):
                os.makedirs(calibration_directory)
            self.treeview.tree.load(self.experiment_file.nxfilename, 'rw')
            super(ExperimentDialog, self).accept()
        except Exception as error:
            report_error("Defining New Experiment", error)
