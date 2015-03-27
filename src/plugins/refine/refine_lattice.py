from PySide import QtCore, QtGui
import numpy as np
from scipy.optimize import minimize
from nexpy.gui.datadialogs import BaseDialog
from nexpy.gui.mainwindow import report_error
from nexpy.gui.plotview import plotview
from nexusformat.nexus import NeXusError
from nxpeaks.nxrefine import NXRefine, find_nearest


def show_dialog(parent=None):
    try:
        dialog = RefineLatticeDialog(parent)
        dialog.show()
    except NeXusError as error:
        report_error("Refining Lattice", error)


class RefineLatticeDialog(BaseDialog):

    def __init__(self, parent=None):
        super(RefineLatticeDialog, self).__init__(parent)
        try:
            node = self.get_node()
            self.entry = node.nxentry
        except:
            raise NeXusError('Check node selection')
        layout = QtGui.QVBoxLayout()
        grid = QtGui.QGridLayout()
        grid.setSpacing(10)
        self.symmetry_box = QtGui.QComboBox()
        self.symmetry_box.setSizeAdjustPolicy(QtGui.QComboBox.AdjustToContents)
        self.unitcell_a_box = QtGui.QLineEdit()
        self.unitcell_b_box = QtGui.QLineEdit()
        self.unitcell_c_box = QtGui.QLineEdit()
        self.unitcell_alpha_box = QtGui.QLineEdit()
        self.unitcell_beta_box = QtGui.QLineEdit()
        self.unitcell_gamma_box = QtGui.QLineEdit()
        self.wavelength_box = QtGui.QLineEdit()
        self.distance_box = QtGui.QLineEdit()
        self.yaw_box = QtGui.QLineEdit('0.0')
        self.pitch_box = QtGui.QLineEdit('0.0')
        self.roll_box = QtGui.QLineEdit('0.0')
        self.xc_box = QtGui.QLineEdit()
        self.yc_box = QtGui.QLineEdit()
        self.polar_box = QtGui.QLineEdit()
        self.polar_box.editingFinished.connect(self.set_polar_max)
        self.tolerance_box = QtGui.QLineEdit('0.1')
        self.unitcell_a_checkbox = QtGui.QCheckBox()
        self.unitcell_b_checkbox = QtGui.QCheckBox()
        self.unitcell_c_checkbox = QtGui.QCheckBox()
        self.unitcell_alpha_checkbox = QtGui.QCheckBox()
        self.unitcell_beta_checkbox = QtGui.QCheckBox()
        self.unitcell_gamma_checkbox = QtGui.QCheckBox()
        self.wavelength_checkbox = QtGui.QCheckBox()
        self.distance_checkbox = QtGui.QCheckBox()
        self.yaw_checkbox = QtGui.QCheckBox()
        self.pitch_checkbox = QtGui.QCheckBox()
        self.roll_checkbox = QtGui.QCheckBox()
        self.xc_checkbox = QtGui.QCheckBox()
        self.yc_checkbox = QtGui.QCheckBox()
        self.unitcell_a_checkbox.setCheckState(QtCore.Qt.Checked)
        self.unitcell_b_checkbox.setCheckState(QtCore.Qt.Checked)
        self.unitcell_c_checkbox.setCheckState(QtCore.Qt.Checked)
        self.unitcell_alpha_checkbox.setCheckState(QtCore.Qt.Checked)
        self.unitcell_beta_checkbox.setCheckState(QtCore.Qt.Checked)
        self.unitcell_gamma_checkbox.setCheckState(QtCore.Qt.Checked)
        self.yaw_checkbox.setCheckState(QtCore.Qt.Checked)
        self.pitch_checkbox.setCheckState(QtCore.Qt.Checked)
        grid.addWidget(QtGui.QLabel('Symmetry:'), 0, 0)
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
        grid.addWidget(QtGui.QLabel('Max. Polar Angle (deg):'), 14, 0)
        grid.addWidget(QtGui.QLabel('Polar Angle Tolerance:'), 15, 0)
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
        grid.addWidget(self.polar_box, 14, 1)
        grid.addWidget(self.tolerance_box, 15, 1)
        fit_label = QtGui.QLabel('Fit?')
        header_font = QtGui.QFont()
        header_font.setBold(True)
        fit_label.setFont(header_font)
        grid.addWidget(fit_label, 0, 2)
        grid.addWidget(self.unitcell_a_checkbox, 1, 2)
        grid.addWidget(self.unitcell_b_checkbox, 2, 2)
        grid.addWidget(self.unitcell_c_checkbox, 3, 2)
        grid.addWidget(self.unitcell_alpha_checkbox, 4, 2)
        grid.addWidget(self.unitcell_beta_checkbox, 5, 2)
        grid.addWidget(self.unitcell_gamma_checkbox, 6, 2)
        grid.addWidget(self.wavelength_checkbox, 7, 2)
        grid.addWidget(self.distance_checkbox, 8, 2)
        grid.addWidget(self.yaw_checkbox, 9, 2)
        grid.addWidget(self.pitch_checkbox, 10, 2)
        grid.addWidget(self.roll_checkbox, 11, 2)
        grid.addWidget(self.xc_checkbox, 12, 2)
        grid.addWidget(self.yc_checkbox, 13, 2)
        layout.addLayout(grid)
        button_layout = QtGui.QHBoxLayout()
        self.plot_button = QtGui.QPushButton('Plot')
        self.plot_button.clicked.connect(self.plot_peaks)
        self.refine_button = QtGui.QPushButton('Refine')
        self.refine_button.clicked.connect(self.refine_parameters)
        self.save_button = QtGui.QPushButton('Save')
        self.save_button.clicked.connect(self.write_parameters)
        button_layout.addWidget(self.plot_button)
        button_layout.addWidget(self.refine_button)
        button_layout.addWidget(self.save_button)
        layout.addLayout(button_layout)
        layout.addWidget(self.buttonbox())
        self.setLayout(layout)
        self.setWindowTitle('Refining Lattice')

        self.refine = NXRefine(self.entry)
        self.refine.read_parameters()
        self.update_parameters()
        for symmetry in self.refine.symmetries:
            self.symmetry_box.addItem(symmetry)
        if self.refine.symmetry:
            self.symmetry_box.setCurrentIndex(self.symmetry_box.findText(self.refine.symmetry))
        else:
            self.symmetry_box.setCurrentIndex(self.symmetry_box.findText(self.guess_symmetry()))
        self.set_symmetry()
        self.symmetry_box.currentIndexChanged.connect(self.set_symmetry)
        polar_min, polar_max = plotview.xaxis.get_limits()
        if (polar_max < self.refine.polar_angle.min() or 
            polar_max > 1.5*self.refine.polar_angle.max()):
            polar_max = self.refine.polar_angle.max()
        self.polar_box.setText(str(polar_max))
        self.refine.set_polar_max(polar_max)

    def update_parameter(self, box, value):
        if value is not None:
            box.setText(str(value))

    def update_parameters(self):
        self.update_parameter(self.unitcell_a_box, self.refine.a)
        self.update_parameter(self.unitcell_b_box, self.refine.b)
        self.update_parameter(self.unitcell_c_box, self.refine.c)
        self.update_parameter(self.unitcell_alpha_box, self.refine.alpha)
        self.update_parameter(self.unitcell_beta_box, self.refine.beta)
        self.update_parameter(self.unitcell_gamma_box, self.refine.gamma)
        self.update_parameter(self.wavelength_box, self.refine.wavelength)
        self.update_parameter(self.distance_box, self.refine.distance)
        self.update_parameter(self.yaw_box, self.refine.yaw)
        self.update_parameter(self.pitch_box, self.refine.pitch)
        self.update_parameter(self.roll_box, self.refine.roll)
        self.update_parameter(self.xc_box, self.refine.xc)
        self.update_parameter(self.yc_box, self.refine.yc)

    def transfer_parameters(self):
        self.refine.a, self.refine.b, self.refine.c, \
            self.refine.alpha, self.refine.beta, self.refine.gamma = self.get_lattice_parameters()
        self.refine.wavelength = self.get_wavelength()
        self.refine.distance = self.get_distance()
        self.refine.yaw, self.refine.pitch, self.refine.roll = self.get_tilts()
        self.refine.xc, self.refine.yc = self.get_centers()
        self.refine.polar_max = self.get_polar_max()
        self.refine.polar_tol = self.get_tolerance()

    def write_parameters(self):
        try:
            polar_angles, azimuthal_angles = self.refine.calculate_angles(
                                                 self.refine.xp, self.refine.yp)
            self.refine.write_angles(polar_angles, azimuthal_angles)
            self.refine.write_parameters()
        except NeXusError as error:
            report_error('Refining Lattice', error)

    def get_symmetry(self):
        return self.symmetry_box.currentText()

    def set_symmetry(self):
        self.refine.symmetry = self.get_symmetry()
        self.refine.set_symmetry()
        self.update_parameters()
        if self.refine.symmetry == 'cubic':
            self.unitcell_b_checkbox.setCheckState(QtCore.Qt.Unchecked)
            self.unitcell_c_checkbox.setCheckState(QtCore.Qt.Unchecked)
            self.unitcell_alpha_checkbox.setCheckState(QtCore.Qt.Unchecked)
            self.unitcell_beta_checkbox.setCheckState(QtCore.Qt.Unchecked)
            self.unitcell_gamma_checkbox.setCheckState(QtCore.Qt.Unchecked)
        elif self.refine.symmetry == 'tetragonal':
            self.unitcell_b_checkbox.setCheckState(QtCore.Qt.Unchecked)
            self.unitcell_alpha_checkbox.setCheckState(QtCore.Qt.Unchecked)
            self.unitcell_beta_checkbox.setCheckState(QtCore.Qt.Unchecked)
            self.unitcell_gamma_checkbox.setCheckState(QtCore.Qt.Unchecked)
        elif self.refine.symmetry == 'orthorhombic':
            self.unitcell_alpha_checkbox.setCheckState(QtCore.Qt.Unchecked)
            self.unitcell_beta_checkbox.setCheckState(QtCore.Qt.Unchecked)
            self.unitcell_gamma_checkbox.setCheckState(QtCore.Qt.Unchecked)
        elif self.refine.symmetry == 'hexagonal':
            self.unitcell_b_checkbox.setCheckState(QtCore.Qt.Unchecked)
            self.unitcell_alpha_checkbox.setCheckState(QtCore.Qt.Unchecked)
            self.unitcell_beta_checkbox.setCheckState(QtCore.Qt.Unchecked)
            self.unitcell_gamma_checkbox.setCheckState(QtCore.Qt.Unchecked)
        elif self.refine.symmetry == 'monoclinic':
            self.unitcell_alpha_checkbox.setCheckState(QtCore.Qt.Unchecked)
            self.unitcell_gamma_checkbox.setCheckState(QtCore.Qt.Unchecked)

    def guess_symmetry(self):
        self.refine.a, self.refine.b, self.refine.c, \
            self.refine.alpha, self.refine.beta, self.refine.gamma = self.get_lattice_parameters()
        return self.refine.guess_symmetry()

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

    def get_tilts(self):
        return (np.float32(self.yaw_box.text()),
                np.float32(self.pitch_box.text()),
                np.float32(self.roll_box.text()))

    def get_centers(self):
        return np.float32(self.xc_box.text()), np.float32(self.yc_box.text())

    def get_polar_max(self):
        return np.float32(self.polar_box.text())

    def set_polar_max(self):
        self.refine.set_polar_max(self.get_polar_max())

    def get_tolerance(self):
        return np.float32(self.tolerance_box.text())

    def plot_peaks(self):
        self.transfer_parameters()
        self.refine.polar_max = self.get_polar_max()
        self.refine.plot_peaks(self.refine.x, self.refine.y)
        self.refine.plot_rings()

    def refine_parameters(self):
        self.initialize_fit()
        p0 = np.array([p.values()[0] for p in self.parameters])
        result = minimize(self.residuals, p0, method='nelder-mead',
                              options={'xtol': 1e-6, 'disp': True})
        self.get_parameters(result.x)
        self.refine.set_symmetry()
        self.update_parameters()

    def initialize_fit(self):
        self.parameters = []
        if self.unitcell_a_checkbox.isChecked():
            self.parameters.append({'a':self.refine.a})
        if self.unitcell_b_checkbox.isChecked():
            self.parameters.append({'b':self.refine.b})
        if self.unitcell_c_checkbox.isChecked():
            self.parameters.append({'c':self.refine.c})
        if self.unitcell_alpha_checkbox.isChecked():
            self.parameters.append({'alpha':self.refine.alpha})
        if self.unitcell_beta_checkbox.isChecked():
            self.parameters.append({'beta':self.refine.beta})
        if self.unitcell_gamma_checkbox.isChecked():
            self.parameters.append({'gamma':self.refine.gamma})
        if self.wavelength_checkbox.isChecked():
            self.parameters.append({'wavelength':self.refine.wavelength})
        if self.distance_checkbox.isChecked():
            self.parameters.append({'distance':self.refine.distance})
        if self.yaw_checkbox.isChecked():
            self.parameters.append({'yaw':self.refine.yaw})
        if self.pitch_checkbox.isChecked():
            self.parameters.append({'pitch':self.refine.pitch})
        if self.roll_checkbox.isChecked():
            self.parameters.append({'roll':self.refine.roll})
        if self.xc_checkbox.isChecked():
            self.parameters.append({'xc':self.refine.xc})
        if self.yc_checkbox.isChecked():
            self.parameters.append({'yc':self.refine.yc})
        return self.parameters

    def get_parameters(self, p):
        i = 0
        for key in [x.keys()[0] for x in self.parameters]:
            self.refine.__dict__[key] = p[i]
            i += 1
        self.refine.set_symmetry()

    def residuals(self, p):
        self.get_parameters(p)
        polar_angles, _ = self.refine.calculate_angles(self.refine.x, self.refine.y)
        rings = self.refine.calculate_rings()
        residuals = np.array([find_nearest(rings, polar_angle) - polar_angle 
                              for polar_angle in polar_angles])
        return np.sum(residuals**2)





