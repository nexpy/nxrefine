from PySide import QtGui
import numpy as np
from nexpy.gui.datadialogs import BaseDialog
from nexpy.gui.mainwindow import report_error
from nexpy.gui.plotview import plotview
from nexpy.api.nexus import NeXusError, NXfield
from nexpy.api.nexus import NXdetector, NXinstrument, NXsample
from nxpeaks.unitcell import unitcell, radians, degrees
from nxrefine import NXRefine


def show_dialog(parent=None):
    try:
        dialog = OrientationDialog(parent)
        dialog.show()
    except NeXusError as error:
        report_error("Refining Orientation", error)
        

class OrientationDialog(BaseDialog):

    def __init__(self, parent=None):
        super(OrientationDialog, self).__init__(parent)
        node = self.get_node()
        self.root = node.nxroot
        if self.root.nxfilemode == 'r':
            raise NeXusError('NeXus file opened as readonly')

        layout = QtGui.QVBoxLayout()
        grid = QtGui.QGridLayout()
        grid.setSpacing(10)
        self.start_box = QtGui.QLineEdit('0.0')
        self.start_box.editingFinished.connect(self.set_omega)
        self.step_box = QtGui.QLineEdit('0.1')
        self.step_box.editingFinished.connect(self.set_omega)
        self.polar_box = QtGui.QLineEdit('4.0')
        self.polar_box.editingFinished.connect(self.set_polar_max)
        self.ring1_box = QtGui.QComboBox()
        self.ring1_box.setSizeAdjustPolicy(QtGui.QComboBox.AdjustToContents)
        self.ring1_box.currentIndexChanged.connect(self.set_rings)
        self.peak1_box = QtGui.QComboBox()
        self.peak1_box.setSizeAdjustPolicy(QtGui.QComboBox.AdjustToContents)
        self.ring2_box = QtGui.QComboBox()
        self.ring2_box.setSizeAdjustPolicy(QtGui.QComboBox.AdjustToContents)
        self.ring2_box.currentIndexChanged.connect(self.set_rings)
        self.peak2_box = QtGui.QComboBox()
        self.peak2_box.setSizeAdjustPolicy(QtGui.QComboBox.AdjustToContents)
        grid.addWidget(QtGui.QLabel('Omega Start (deg): '), 0, 0)
        grid.addWidget(QtGui.QLabel('Omega Step (deg):'), 1, 0)
        grid.addWidget(QtGui.QLabel('Max. Polar Angle:'), 2, 0)
        grid.addWidget(QtGui.QLabel('Ring 1:'), 3, 0)
        grid.addWidget(QtGui.QLabel('Ring 2:'), 4, 0)
        grid.addWidget(self.start_box, 0, 1)
        grid.addWidget(self.step_box, 1, 1)
        grid.addWidget(self.polar_box, 2, 1)
        grid.addWidget(self.ring1_box, 3, 1)
        grid.addWidget(self.peak1_box, 3, 2)
        grid.addWidget(self.ring2_box, 4, 1)
        grid.addWidget(self.peak2_box, 4, 2)
        layout.addLayout(grid)
        button_layout = QtGui.QHBoxLayout()
        self.orient_button = QtGui.QPushButton('Orient')
        self.orient_button.clicked.connect(self.orient)
        self.save_button = QtGui.QPushButton('Save')
        self.save_button.clicked.connect(self.write_parameters)
        button_layout.addWidget(self.orient_button)
        button_layout.addWidget(self.save_button)
        layout.addLayout(button_layout)
        layout.addWidget(self.buttonbox())
        self.setLayout(layout)
        self.setWindowTitle('Refining Orientation')

        self.refine = NXRefine(self.root)
        self.refine.read_parameters()
        self.initialize_rings()
        self.set_polar_max()

    def initialize_rings(self):
        self.refine.set_polar_max(self.get_polar_max())
        hkls = self.refine.get_hkls()
        self.ring1_box.clear()
        for hkl in hkls:
            self.ring1_box.addItem(str(hkl))
            self.ring1_box.setCurrentIndex(0)
        self.ring2_box.clear()
        for hkl in hkls:
            self.ring2_box.addItem(str(hkl))
            self.ring2_box.setCurrentIndex(0)
        self.set_peaks()

    def get_rings(self):
        r1 = self.ring1_box.currentText()
        try:
            ring1 = map(np.int32, r1[1:-1].split(','))
        except Exception:
            ring1 = [0,0,1]
        r2 = self.ring2_box.currentText()
        try:
            ring2 = map(np.int32, r2[1:-1].split(','))
        except Exception:
            ring2 = ring1
        return tuple(ring1), tuple(ring2)

    def set_rings(self):
        self.set_peaks()

    def get_peaks(self):
        r1, r2 = self.get_rings()
        ring1, ring2 = self.refine.find_ring(*r1), self.refine.find_ring(*r2)
        return (self.refine.find_ring_indices(ring1)[self.peak1_box.currentIndex()],
                self.refine.find_ring_indices(ring2)[self.peak2_box.currentIndex()])

    def set_peaks(self):
        r1, r2 = self.get_rings()
        ring1, ring2 = self.refine.find_ring(*r1), self.refine.find_ring(*r2)
        self.peak1_box.clear()
        for i in self.refine.find_ring_indices(ring1):
            peak = (np.int32(np.round(self.refine.xp[i],0)),
                    np.int32(np.round(self.refine.yp[i],0)),
                    np.int32(np.round(self.refine.zp[i],0)))
            self.peak1_box.addItem(str(peak).strip())
        self.peak2_box.clear()
        for i in self.refine.find_ring_indices(ring2):
            peak = (np.int32(np.round(self.refine.xp[i],0)),
                    np.int32(np.round(self.refine.yp[i],0)),
                    np.int32(np.round(self.refine.zp[i],0)))
            self.peak2_box.addItem(str(peak).strip())

    def get_omega(self):
        return (np.float32(self.start_box.text()),
                np.float32(self.step_box.text())) 

    def set_omega(self):
        self.refine.omega_start, self.refine.omega_step = self.get_omega() 

        return np.float32(self.polar_box.text())

    def get_polar_max(self):
        return np.float32(self.polar_box.text())

    def set_polar_max(self):
        self.refine.set_polar_max(self.get_polar_max())
        self.initialize_rings()

    def orient(self):
        self.refine.omega_start, self.refine.omega_step = self.get_omega()
        i, j = self.get_peaks()
        self.refine.UBmat = self.refine.orient(i, j)
        self.list_orientations()

    def list_orientations(self):
        message_box = BaseDialog(self)
        message_box.setMinimumWidth(600)
        text_box = QtGui.QTextEdit()
        text_box.setTabStopWidth(40)
        lines = []
        for i in self.refine.idx:
           x, y, z = self.refine.xp[i], self.refine.yp[i], self.refine.zp[i]
           h, k, l = self.refine.hkli(i)
           lines.append('Peak %s:\tx, y, z =\t%s\t%s\t%s\t\th,k,l =\t%s\t%s\t%s' % 
                         (i, 
                         np.int32(np.round(x,0)), 
                         np.int32(np.round(y,0)),
                         np.int32(np.round(z,0)),
                         np.round(h,2), 
                         np.round(k,2), 
                         np.round(l,2)))
        text_box.setText('\n'.join(lines))
        layout = QtGui.QVBoxLayout()
        layout.addWidget(text_box)
        layout.addWidget(self.buttonbox()) 
        message_box.setLayout(layout)
        message_box.show()

    def write_parameters(self):
        try:
            self.refine.write_parameters()
        except NeXusError as error:
            report_error('Refining Orientation', error)
