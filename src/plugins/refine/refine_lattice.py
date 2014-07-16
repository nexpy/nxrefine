from PySide import QtGui
import numpy as np
from nexpy.gui.datadialogs import BaseDialog
from nexpy.gui.mainwindow import report_error
from nexpy.gui.plotview import plotview
from nexpy.api.nexus import NeXusError, NXfield
from nexpy.api.nexus import NXdetector, NXinstrument, NXsample
from nxpeaks.unitcell import unitcell, radians, degrees


def show_dialog(parent=None):
    try:
        dialog = RefineLatticeDialog(parent)
        dialog.exec_()
    except NeXusError as error:
        report_error("Refining Lattice", error)
        

class RefineLatticeDialog(BaseDialog):

    def __init__(self, parent=None):
        super(RefineLatticeDialog, self).__init__(parent)
        node = self.get_node()
        self.root = node.nxroot
        if self.root.nxfilemode == 'r':
            raise NeXusError('NeXus file opened as readonly')
        layout = QtGui.QVBoxLayout()
        grid = QtGui.QGridLayout()
        grid.setSpacing(10)
        self.symmetry_box = QtGui.QComboBox()
        self.unitcell_a_box = QtGui.QLineEdit()
        self.unitcell_b_box = QtGui.QLineEdit()
        self.unitcell_c_box = QtGui.QLineEdit()
        self.unitcell_alpha_box = QtGui.QLineEdit()
        self.unitcell_beta_box = QtGui.QLineEdit()
        self.unitcell_gamma_box = QtGui.QLineEdit()
        self.wavelength_box = QtGui.QLineEdit()
        self.distance_box = QtGui.QLineEdit()
        self.yaw_box = QtGui.QLineEdit()
        self.pitch_box = QtGui.QLineEdit()
        self.roll_box = QtGui.QLineEdit()
        self.xc_box = QtGui.QLineEdit()
        self.yc_box = QtGui.QLineEdit()
        self.unitcell_a_checkbox = QtGui.QCheckBox()
        self.unitcell_b_checkbox = QtGui.QCheckBox()
        self.unitcell_c_checkbox = QtGui.QCheckBox()
        self.unitcell_alpha_checkbox = QtGui.QCheckBox()
        self.unitcell_beta_checkbox = QtGui.QCheckBox()
        self.unitcell_gamma_checkbox = QtGui.QCheckBox()
        self.wavelength_checkbox = QtGui.QLineEdit()
        self.distance_checkbox = QtGui.QCheckBox()
        self.yaw_checkbox = QtGui.QCheckBox()
        self.pitch_checkbox = QtGui.QCheckBox()
        self.roll_checkbox = QtGui.QCheckBox()
        self.xc_checkbox = QtGui.QCheckBox()
        self.yc_checkbox = QtGui.QCheckBox()
        grid.addWidget(QtGui.QLabel('Unit Cell - a (Ang):'), 1, 0)
        grid.addWidget(QtGui.QLabel('Unit Cell - b (Ang):'), 2, 0)
        grid.addWidget(QtGui.QLabel('Unit Cell - c (Ang):'), 3, 0)
        grid.addWidget(QtGui.QLabel('Unit Cell - alpha (deg):'), 4, 0)
        grid.addWidget(QtGui.QLabel('Unit Cell - beta (deg):'), 5, 0)
        grid.addWidget(QtGui.QLabel('Unit Cell - gamma (deg):'), 6, 0)
        grid.addWidget(QtGui.QLabel('Wavelength (Ang):'), 7, 0)
        grid.addWidget(QtGui.QLabel('Distance (mm):'), 8, 0)
        grid.addWidget(QtGui.QLabel('Yaw (deg):'), 9, 0)
        grid.addWidget(QtGui.QLabel('Pitch (deg):'), 10, 0)
        grid.addWidget(QtGui.QLabel('Roll (deg):'), 11, 0)
        grid.addWidget(QtGui.QLabel('Beam Center - x:'), 12, 0)
        grid.addWidget(QtGui.QLabel('Beam Center - y:'), 13, 0)
        grid.addWidget(self.symmetry_box, 0, 1)
        grid.addWidget(self.unitcell_a_box, 1, 1)
        grid.addWidget(self.unitcell_b_box, 2, 1)
        grid.addWidget(self.unitcell_c_box, 3, 1)
        grid.addWidget(self.unitcell_alpha_box, 4, 1)
        grid.addWidget(self.unitcell_beta_box, 5, 1)
        grid.addWidget(self.unitcell_gamma_box, 6, 1)
        grid.addWidget(self.wavelength_box, 7, 1)
        grid.addWidget(self.distance_box, 8, 1)
        grid.addWidget(self.yaw_box, 9, 1)
        grid.addWidget(self.pitch_box, 10, 1)
        grid.addWidget(self.roll_box, 11, 1)
        grid.addWidget(self.xc_box, 12, 1)
        grid.addWidget(self.yc_box, 13, 1)
        grid.addWidget(self.unitcell_a_checkbox, 1, 2)
        grid.addWidget(self.unitcell_b_checkbox, 2, 2)
        grid.addWidget(self.unitcell_c_checkbox, 3, 2)
        grid.addWidget(self.unitcell_alpha_checkbox, 4, 2)
        grid.addWidget(self.unitcell_beta_checkbox, 5, 2)
        grid.addWidget(self.unitcell_gamma_checkbox, 6, 2)
        grid.addWidget(self.wavelength_box, 7, 2)
        grid.addWidget(self.distance_checkbox, 8, 2)
        grid.addWidget(self.yaw_checkbox, 9, 2)
        grid.addWidget(self.pitch_checkbox, 10, 2)
        grid.addWidget(self.roll_checkbox, 11, 2)
        grid.addWidget(self.xc_checkbox, 12, 2)
        grid.addWidget(self.yc_checkbox, 13, 2)
        layout.addLayout(grid)
        button_layout = QtGui.QHBoxLayout()
        self.plot_button = QtGui.QPushButton('Plot Angles')
        self.plot_button.clicked.connect(self.plot_angles)
        self.refine_button = QtGui.QPushButton('Refine Parameters')
        self.refine_button.clicked.connect(self.refine_parameters)
        button_layout.addWidget(self.plot_button)
        button_layout.addWidget(self.refine_button)
        layout.addLayout(button_layout)
        layout.addWidget(self.buttonbox(save=True))
        self.setLayout(layout)
        self.setWindowTitle('Refining Lattice')

        self.read_parameters()

    def get_symmetry(self):
        return self.symmetry_box.currentText()

    def get_lattice_parameters(self):
        return (np.float32(self.unitcell_a_box.text()),
                np.float32(self.unitcell_b_box.text()),
                np.float32(self.unitcell_c_box.text()),
                np.float32(self.unitcell_alpha_box.text()),
                np.float32(self.unitcell_beta_box.text()),
                np.float32(self.unitcell_gamma_box.text())) 

    def get_wavelength(self):
        return np.float32(self.wavelength_box.text())

    def get_distance(self):
        return np.float32(self.distance_box.text())

    def get_detector_parameters(self):
        return (np.float32(self.distance_box.text()),
                np.float32(self.yaw_box.text()),
                np.float32(self.pitch_box.text()),
                np.float32(self.roll_box.text()),
                np.float32(self.xc_box.text()),
                np.float32(self.yc_box.text())) 

    def get_centers(self):
        return np.float32(self.xc_box.text()), np.float32(self.yc_box.text())

    def read_parameters(self):
        try:
            self.unitcell_a_box.setText(str(self.root['entry/sample/unitcell_a']))
        except NeXusError:
            pass
        try:
            self.unitcell_b_box.setText(str(self.root['entry/sample/unitcell_b']))
        except NeXusError:
            pass
        try:
            self.unitcell_c_box.setText(str(self.root['entry/sample/unitcell_c']))
        except NeXusError:
            pass
        try:
            self.unitcell_alpha_box.setText(str(self.root['entry/sample/unitcell_alpha']))
        except NeXusError:
            pass
        try:
            self.unitcell_beta_box.setText(str(self.root['entry/sample/unitcell_beta']))
        except NeXusError:
            pass
        try:
            self.unitcell_gamma_box.setText(str(self.root['entry/sample/unitcell_gamma']))
        except NeXusError:
            pass
        try:
            self.wavelength_box.setText(str(self.root['entry/instrument/monochromator/wavelength']))
        except NeXusError:
            pass
        try:
            self.distance_box.setText(str(self.root['entry/instrument/detector/distance']))
        except NeXusError:
            pass
        try:
            self.unitcell_gamma_box.setText(str(self.root['entry/instrument/detector/yaw']))
        except NeXusError:
            pass
        try:
            self.unitcell_gamma_box.setText(str(self.root['entry/instrument/detector/pitch']))
        except NeXusError:
            pass
        try:
            self.unitcell_gamma_box.setText(str(self.root['entry/instrument/detector/roll']))
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
        symmetries = ['P', 'A', 'B', 'C', 'I', 'F', 'R']
        for symmetry in symmetries:
            self.symmetry_box.addItem(symmetry)
        try:
            symmetry = str(self.root['entry/sample/lattice_centring'])
            self.symmetry_box.setCurrentIndex(self.symmetry_box.findText(symmetry))
        except NeXusError:
            pass

    def write_parameters(self):
        if 'instrument' not in self.root.entry.entries:
            self.root.entry.instrument = NXinstrument()
        if 'detector' not in self.root.entry.instrument.entries:
            self.root.entry.instrument.detector = NXdetector()
        if 'monochromator' not in self.root.entry.instrument.entries:
            self.root.entry.instrument.monochromator = NXmonochromator()
        if 'sample' not in self.root.entry.entries:
            self.root.entry.sample = NXsample()
        a, b, c, alpha, beta, gamma = self.get_lattice_parameters()
        self.root.entry.sample.unitcell_a = a
        self.root.entry.sample.unitcell_b = b
        self.root.entry.sample.unitcell_c = c
        self.root.entry.sample.unitcell_alpha = alpha
        self.root.entry.sample.unitcell_beta = beta
        self.root.entry.sample.unitcell_gamma = gamma
        self.root.entry.sample.lattice_centring = self.get_symmetry()
        self.root.entry.instrument.monochromator.wavelength = self.get_wavelength()
        self.root.entry.instrument.detector.distance = self.get_distance()
        xc, yc = self.get_centers()
        self.root.entry.instrument.detector.beam_center_x = xc
        self.root.entry.instrument.detector.beam_center_y = yc

    def plot_angles(self):
        try:
            polar_min, polar_max = plotview.plot.xaxis.get_limits()
            wavelength = self.root.entry.instrument.monochromator.wavelength
            ds_max = 2 * np.sin(radians(polar_max/2)) / wavelength
            cell = unitcell(self.get_lattice_parameters(), self.get_symmetry())
            dss = set(sorted([x[0] for x in cell.gethkls(ds_max)]))
            polar_angles = []
            for ds in dss:
                polar_angles.append(2*degrees(np.arcsin(wavelength*ds/2)))
            polar_angles = sorted(polar_angles)
            ymin, ymax = plotview.plot.yaxis.get_limits()
            plotview.figure.axes[0].vlines(polar_angles, ymin, ymax,
                                           colors='r', linestyles='dotted')
            plotview.redraw()
        except NeXusError as error:
            report_error('Plotting Lattice', error)

    def accept(self):
        try:
            self.write_parameters()
            super(RefineLatticeDialog, self).accept()
        except NeXusError as error:
            report_error('Refining Lattice', error)
