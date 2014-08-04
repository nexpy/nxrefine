from PySide import QtGui
import numpy as np
from nexpy.gui.datadialogs import BaseDialog
from nexpy.gui.mainwindow import report_error
from nxrefine import NXRefine


def show_dialog(parent=None):
    try:
        dialog = CalculateDialog(parent)
        dialog.show()
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
        grid.addWidget(QtGui.QLabel('Wavelength (Ang):'), 0, 0)
        grid.addWidget(QtGui.QLabel('Detector Distance (mm):'), 1, 0)
        grid.addWidget(QtGui.QLabel('Beam Center - x:'), 2, 0)
        grid.addWidget(QtGui.QLabel('Beam Center - y:'), 3, 0)
        grid.addWidget(QtGui.QLabel('Pixel Size (mm):'), 4, 0)
        grid.addWidget(self.wavelength_box, 0, 1)
        grid.addWidget(self.distance_box, 1, 1)
        grid.addWidget(self.xc_box, 2, 1)
        grid.addWidget(self.yc_box, 3, 1)
        grid.addWidget(self.pixel_box, 4, 1)
        layout.addLayout(grid)
        button_layout = QtGui.QHBoxLayout()
        self.plot_button = QtGui.QPushButton('Plot')
        self.plot_button.clicked.connect(self.plot_peaks)
        self.save_button = QtGui.QPushButton('Save')
        self.save_button.clicked.connect(self.write_parameters)
        button_layout.addWidget(self.plot_button)
        button_layout.addWidget(self.save_button)
        layout.addLayout(button_layout)
        layout.addWidget(self.buttonbox())
        self.setLayout(layout)
        self.setWindowTitle('Calculate Angles')

        self.refine = NXRefine(self.root)
        self.refine.read_parameters()
        self.update_parameters()

    def update_parameter(self, box, value):
        if value is not None:
            box.setText(str(value))

    def update_parameters(self):
        self.update_parameter(self.wavelength_box, self.refine.wavelength)
        self.update_parameter(self.distance_box, self.refine.distance)
        self.update_parameter(self.xc_box, self.refine.xc)
        self.update_parameter(self.yc_box, self.refine.yc)
        self.update_parameter(self.pixel_box, self.refine.pixel_size)

    def get_wavelength(self):
        return np.float32(self.wavelength_box.text())

    def get_distance(self):
        return np.float32(self.distance_box.text())

    def get_centers(self):
        return np.float32(self.xc_box.text()), np.float32(self.yc_box.text())

    def get_pixel_size(self):
        return np.float32(self.pixel_box.text())

    def get_parameters(self):
        self.refine.wavelength = self.get_wavelength()
        self.refine.distance = self.get_distance()
        self.refine.xc, self.refine.yc = self.get_centers()
        self.refine.pixel_size = self.get_pixel_size()
        self.refine.yaw = self.refine.pitch = self.refine.roll = None

    def plot_peaks(self):
        try:
            self.get_parameters()
            self.refine.plot_peaks(self.refine.xp, self.refine.yp)
        except NeXusError as error:
            report_error('Calculating Angles', error)

    def write_parameters(self):
        try:
            self.get_parameters()
            polar_angles, azimuthal_angles = self.refine.calculate_angles(
                                                 self.refine.xp, self.refine.yp)
            self.refine.write_angles(polar_angles, azimuthal_angles)
            self.refine.write_parameters()
        except NeXusError as error:
            report_error('Calculating Angles', error)
