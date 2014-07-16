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
        dialog = LatticeDialog(parent)
        dialog.exec_()
    except NeXusError as error:
        report_error("Defining Lattice", error)
        

class LatticeDialog(BaseDialog):

    def __init__(self, parent=None):
        super(LatticeDialog, self).__init__(parent)
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
        grid.addWidget(QtGui.QLabel('Cell Symmetry: '), 0, 0)
        grid.addWidget(QtGui.QLabel('Unit Cell - a (Ang):'), 1, 0)
        grid.addWidget(QtGui.QLabel('Unit Cell - b (Ang):'), 2, 0)
        grid.addWidget(QtGui.QLabel('Unit Cell - c (Ang):'), 3, 0)
        grid.addWidget(QtGui.QLabel('Unit Cell - alpha (deg):'), 4, 0)
        grid.addWidget(QtGui.QLabel('Unit Cell - beta (deg):'), 5, 0)
        grid.addWidget(QtGui.QLabel('Unit Cell - gamma (deg):'), 6, 0)
        grid.addWidget(self.symmetry_box, 0, 1)
        grid.addWidget(self.unitcell_a_box, 1, 1)
        grid.addWidget(self.unitcell_b_box, 2, 1)
        grid.addWidget(self.unitcell_c_box, 3, 1)
        grid.addWidget(self.unitcell_alpha_box, 4, 1)
        grid.addWidget(self.unitcell_beta_box, 5, 1)
        grid.addWidget(self.unitcell_gamma_box, 6, 1)
        layout.addLayout(grid)
        self.plot_button = QtGui.QPushButton('Plot Angles')
        self.plot_button.clicked.connect(self.plot_angles)
        layout.addWidget(self.plot_button)
        layout.addWidget(self.buttonbox(save=True))
        self.setLayout(layout)
        self.setWindowTitle('Defining Lattice')

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
        symmetries = ['P', 'A', 'B', 'C', 'I', 'F', 'R']
        for symmetry in symmetries:
            self.symmetry_box.addItem(symmetry)
        try:
            symmetry = str(self.root['entry/sample/lattice_centring'])
            self.symmetry_box.setCurrentIndex(self.symmetry_box.findText(symmetry))
        except NeXusError:
            pass

    def write_parameters(self):
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
            super(LatticeDialog, self).accept()
        except NeXusError as error:
            report_error('Defining Lattice', error)
