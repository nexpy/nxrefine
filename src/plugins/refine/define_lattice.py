from PySide import QtGui
import numpy as np
from nexpy.gui.datadialogs import BaseDialog
from nexpy.gui.mainwindow import report_error
from nexpy.gui.plotview import plotview
from nexusformat.nexus import NeXusError
from nxrefine import NXRefine


def show_dialog(parent=None):
    try:
        dialog = LatticeDialog(parent)
        dialog.show()
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
        self.centring_box = QtGui.QComboBox()
        self.unitcell_a_box = QtGui.QLineEdit()
        self.unitcell_b_box = QtGui.QLineEdit()
        self.unitcell_c_box = QtGui.QLineEdit()
        self.unitcell_alpha_box = QtGui.QLineEdit()
        self.unitcell_beta_box = QtGui.QLineEdit()
        self.unitcell_gamma_box = QtGui.QLineEdit()
        grid.addWidget(QtGui.QLabel('Cell Centring: '), 0, 0)
        grid.addWidget(QtGui.QLabel('Unit Cell - a (Ang):'), 1, 0)
        grid.addWidget(QtGui.QLabel('Unit Cell - b (Ang):'), 2, 0)
        grid.addWidget(QtGui.QLabel('Unit Cell - c (Ang):'), 3, 0)
        grid.addWidget(QtGui.QLabel('Unit Cell - alpha (deg):'), 4, 0)
        grid.addWidget(QtGui.QLabel('Unit Cell - beta (deg):'), 5, 0)
        grid.addWidget(QtGui.QLabel('Unit Cell - gamma (deg):'), 6, 0)
        grid.addWidget(self.centring_box, 0, 1)
        grid.addWidget(self.unitcell_a_box, 1, 1)
        grid.addWidget(self.unitcell_b_box, 2, 1)
        grid.addWidget(self.unitcell_c_box, 3, 1)
        grid.addWidget(self.unitcell_alpha_box, 4, 1)
        grid.addWidget(self.unitcell_beta_box, 5, 1)
        grid.addWidget(self.unitcell_gamma_box, 6, 1)
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
        self.setWindowTitle('Defining Lattice')

        self.refine = NXRefine(self.root)
        self.refine.read_parameters()
        self.update_parameters()

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
        for centring in self.refine.centrings:
            self.centring_box.addItem(centring)
        if self.refine.centring:
            self.centring_box.setCurrentIndex(self.centring_box.findText(self.refine.centring))

    def get_centring(self):
        return self.centring_box.currentText()

    def get_lattice_parameters(self):
        return (np.float32(self.unitcell_a_box.text()),
                np.float32(self.unitcell_b_box.text()),
                np.float32(self.unitcell_c_box.text()),
                np.float32(self.unitcell_alpha_box.text()),
                np.float32(self.unitcell_beta_box.text()),
                np.float32(self.unitcell_gamma_box.text())) 

    def get_parameters(self):
        self.refine.a, self.refine.b, self.refine.c, \
            self.refine.alpha, self.refine.beta, self.refine.gamma = self.get_lattice_parameters()
        self.refine.centring = self.get_centring()

    def plot_peaks(self):
        try:
            self.get_parameters()
            self.refine.plot_peaks(self.refine.xp, self.refine.yp)
            polar_min, polar_max = plotview.plot.xaxis.get_limits()
            self.refine.plot_rings(polar_max)
        except NeXusError as error:
            report_error('Plotting Lattice', error)

    def write_parameters(self):
        try:
            self.get_parameters()
            self.refine.write_parameters()
        except NeXusError as error:
            report_error('Defining Lattice', error)
