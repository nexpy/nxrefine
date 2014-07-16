from PySide import QtGui
import numpy as np
from nexpy.gui.datadialogs import BaseDialog
from nexpy.gui.mainwindow import report_error
from nexpy.api.nexus import NeXusError, NXfield
from nexpy.api.nexus import NXdetector, NXinstrument, NXmonochromator


def show_dialog(parent=None):
    try:
        dialog = CalculateDialog(parent)
        dialog.exec_()
    except NeXusError as error:
        report_error("Calculating Angles", error)
        

class CalculateDialog(BaseDialog):

    def __init__(self, parent=None):
        super(CalculateDialog, self).__init__(parent)
        node = self.get_node()
        self.root = node.nxroot
        if self.root.nxfilemode == 'r':
            raise NeXusError('NeXus file opened as readonly')
        layout = QtGui.QVBoxLayout()
        grid = QtGui.QGridLayout()
        grid.setSpacing(10)
        self.wavelength_box = QtGui.QLineEdit()
        self.distance_box = QtGui.QLineEdit()
        self.xc_box = QtGui.QLineEdit()
        self.yc_box = QtGui.QLineEdit()
        self.pixel_box = QtGui.QLineEdit()
        self.peaks_box = QtGui.QComboBox()
        grid.addWidget(QtGui.QLabel('Wavelength (Ang):'), 0, 0)
        grid.addWidget(QtGui.QLabel('Detector Distance (mm):'), 1, 0)
        grid.addWidget(QtGui.QLabel('Beam Center - x:'), 2, 0)
        grid.addWidget(QtGui.QLabel('Beam Center - y:'), 3, 0)
        grid.addWidget(QtGui.QLabel('Pixel Size (mm):'), 4, 0)
        grid.addWidget(QtGui.QLabel('Peaks Group:'), 5, 0)
        grid.addWidget(self.wavelength_box, 0, 1)
        grid.addWidget(self.distance_box, 1, 1)
        grid.addWidget(self.xc_box, 2, 1)
        grid.addWidget(self.yc_box, 3, 1)
        grid.addWidget(self.pixel_box, 4, 1)
        grid.addWidget(self.peaks_box, 5, 1)
        layout.addLayout(grid)
        layout.addWidget(self.buttonbox(save=True))
        self.setLayout(layout)
        self.setWindowTitle('Calculate Angles')

        self.read_parameters()

    def get_wavelength(self):
        return np.float32(self.wavelength_box.text())

    def get_distance(self):
        return np.float32(self.distance_box.text())

    def get_centers(self):
        return np.float32(self.xc_box.text()), np.float32(self.yc_box.text())

    def get_pixel_size(self):
        return np.float32(self.pixel_box.text())

    def get_peaks(self):
        return self.peaks_box.currentText()

    def read_parameters(self):
        try:
            self.wavelength_box.setText(str(self.root['entry/instrument/monochromator/wavelength']))
        except NeXusError:
            pass
        try:
            self.distance_box.setText(str(self.root['entry/instrument/detector/distance']))
        except NeXusError:
            pass
        try:
            self.xc_box.setText(str(self.root['entry/instrument/detector/beam_center_x']))
        except NeXusError:
            pass
        try:
            self.yc_box.setText(str(self.root['entry/instrument/detector/beam_center_y']))
        except NeXusError:
            pass
        try:
            self.pixel_box.setText(str(self.root['entry/instrument/detector/pixel_size']))
        except NeXusError:
            pass
        for key in self.root.entry.sample.entries:
            if key.startswith('peaks'):
                self.peaks_box.addItem(self.root.entry.sample[key].nxname)

    def write_parameters(self):
        if 'instrument' not in self.root.entry.entries:
            self.root.entry.instrument = NXinstrument()
        if 'detector' not in self.root.entry.instrument.entries:
            self.root.entry.instrument.detector = NXdetector()
        if 'monochromator' not in self.root.entry.instrument.entries:
            self.root.entry.instrument.monochromator = NXmonochromator()
        self.root.entry.instrument.monochromator.wavelength = self.get_wavelength()
        self.root.entry.instrument.detector.distance = self.get_distance()
        xc, yc = self.get_centers()
        self.root.entry.instrument.detector.beam_center_x = xc
        self.root.entry.instrument.detector.beam_center_y = yc
        self.root.entry.instrument.detector.pixel_size = self.get_pixel_size()

    def calculate_angles(self):

        wavelength = self.get_wavelength()
        distance = self.get_distance()
        xc, yc = self.get_centers()
        pixel_size = self.get_pixel_size()
        peaks = self.get_peaks()

        center = np.matrix((xc, yc, 0)).T
        orientation = np.matrix(((0,-1,0), (0,0,1), (-1,0,0)))

        npks = self.root.entry.sample[peaks]['x'].size
        self.polar_angle = NXfield(shape=(npks,), dtype=np.float32)
        self.azimuthal_angle = NXfield(shape=(npks,), dtype=np.float32)
        for i in range(npks):
            x, y = self.root.entry.sample[peaks].x[i], self.root.entry.sample[peaks].y[i]
            peak = np.matrix((x, y, 0)).T - center
            v = np.linalg.norm(pixel_size * np.linalg.inv(orientation) * peak)
            self.polar_angle[i] = np.arctan(v / distance) * 180. / np.pi
            self.azimuthal_angle[i] = np.arctan2(peak[1,0], peak[0,0]) * 180. / np.pi

    def accept(self):
        try:
            self.calculate_angles()
            peaks = self.get_peaks()
            if 'polar_angle' in self.root.entry.sample[peaks].entries:
                del self.root.entry.sample[peaks]['polar_angle']
            self.root.entry.sample[peaks].polar_angle = self.polar_angle
            if 'azimuthal_angle' in self.root.entry.sample[peaks].entries:
                del self.root.entry.sample[peaks]['azimuthal_angle']
            self.root.entry.sample[peaks].azimuthal_angle = self.azimuthal_angle
            self.root.entry.sample[peaks].nxsignal = self.root.entry.sample[peaks].azimuthal_angle
            self.root.entry.sample[peaks].nxaxes = self.root.entry.sample[peaks].polar_angle
            self.write_parameters()
            super(CalculateDialog, self).accept()
        except NeXusError as error:
            report_error('Calculating Angles', error)
