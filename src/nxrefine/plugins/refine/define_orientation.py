import operator
from nexpy.gui.pyqt import QtCore, QtGui, QtWidgets
import numpy as np
import random
from scipy.optimize import leastsq
from nexpy.gui.datadialogs import BaseDialog, GridParameters
from nexpy.gui.plotview import NXPlotView
from nexpy.gui.utils import report_error
from nexusformat.nexus import NeXusError
from nxrefine.nxrefine import NXRefine


def show_dialog():
    try:
        dialog = OrientationDialog()
        dialog.show()
    except NeXusError as error:
        report_error("Defining Orientation", error)
        

class OrientationDialog(BaseDialog):

    def __init__(self, parent=None):
        super(OrientationDialog, self).__init__(parent)

        self.select_entry(self.choose_entry)

        self.refine = NXRefine(self.entry)
        self.refine.read_parameters()

        self.parameters = GridParameters()
        self.parameters.add('phi_start', self.refine.phi_start, 
                            'Phi Start (deg)')
        self.parameters.add('phi_step', self.refine.phi_step, 'Phi Step (deg)')
        self.parameters.add('chi', self.refine.chi, 'Chi (deg)')
        self.parameters.add('omega', self.refine.omega, 'Omega (deg)')
        self.parameters.add('polar', self.refine.polar_max, 
                            'Max. Polar Angle (deg)')
        self.parameters.add('polar_tolerance', self.refine.polar_tolerance, 
                            'Polar Angle Tolerance')
        self.parameters.add('peak_tolerance', self.refine.peak_tolerance, 
                            'Peak Angle Tolerance')
        action_buttons = self.action_buttons(
                             ('Generate Grains', self.generate_grains),
                             ('List Peaks', self.list_peaks))
        self.grain_layout = QtWidgets.QHBoxLayout()
        self.grain_combo = QtWidgets.QComboBox()
        self.grain_combo.setSizeAdjustPolicy(QtWidgets.QComboBox.AdjustToContents)
        self.grain_combo.currentIndexChanged.connect(self.set_grain)
        self.grain_textbox = QtWidgets.QLabel()
        self.grain_layout.addWidget(self.grain_combo)
        self.grain_layout.addStretch()
        self.grain_layout.addWidget(self.grain_textbox)
        bottom_layout = QtWidgets.QHBoxLayout()
        self.result_textbox = QtWidgets.QLabel()
        bottom_layout.addWidget(self.result_textbox)
        bottom_layout.addStretch()
        bottom_layout.addWidget(self.close_buttons())
        self.set_layout(self.entry_layout, self.parameters.grid(), 
                        action_buttons, bottom_layout)
        self.set_title('Defining Orientation')

    def choose_entry(self):
        self.refine = NXRefine(self.entry)
        self.update_parameters()

    def update_parameters(self):
        self.parameters['phi_start'].value = self.refine.phi_start
        self.parameters['phi_step'].value = self.refine.phi_step
        self.parameters['chi'].value = self.refine.chi
        self.parameters['omega'].value = self.refine.omega
        self.parameters['polar'].value = self.refine.polar_max
        self.parameters['polar_tolerance'].value = self.refine.polar_tolerance
        self.parameters['peak_tolerance'].value = self.refine.peak_tolerance

    def get_phi(self):
        return (self.parameters['phi_start'].value,
                self.parameters['phi_step'].value) 

    def set_phi(self):
        self.refine.phi_start, self.refine.phi_step = self.get_phi() 

    def get_chi(self):
        return self.parameters['chi'].value

    def set_chi(self):
        self.refine.chi = self.get_chi() 

    def get_omega(self):
        return self.parameters['omega'].value 

    def set_omega(self):
        self.refine.omega = self.get_omega() 

    @property
    def polar_max(self):
        return self.parameters['polar'].value

    def set_polar_max(self):
        self.refine.polar_max = self.polar_max

    def get_polar_tolerance(self):
        return self.parameters['polar_tolerance'].value

    def set_polar_tolerance(self):
        self.refine.polar_tolerance = self.get_polar_tolerance()

    def get_peak_tolerance(self):
        return self.parameters['peak_tolerance'].value

    def set_peak_tolerance(self):
        self.refine.peak_tolerance = self.get_peak_tolerance()

    def generate_grains(self):
        self.set_polar_max()
        self.refine.generate_grains()
        if self.refine.grains is not None:
            self.layout.insertLayout(2, self.grain_layout)
        self.grain_combo.clear()
        for i in range(len(self.refine.grains)):
            self.grain_combo.addItem('Grain %s' % i)
        self.grain_combo.setCurrentIndex(0)
        self.set_grain()

    def set_grain(self):
        try:
            grain = self.refine.grains[self.get_grain()]
            self.grain_textbox.setText('%s peaks; Score: %.4f' 
                                       % (len(grain), grain.score))
            self.refine.Umat = grain.Umat
            self.refine.primary = grain.primary
            self.refine.secondary = grain.secondary
            self.get_score()
        except:
            self.grain_textbox.setText('')

    def get_grain(self):
        return int(self.grain_combo.currentText().split()[-1])

    def list_peaks(self):
        self.refine.phi_start, self.refine.phi_step = self.get_phi()
        self.refine.chi = self.get_chi()
        self.refine.omega = self.get_omega()
        if self.refine.grains is not None:
            grain = self.refine.grains[self.get_grain()]
            self.refine.Umat = grain.Umat
            self.list_orientations()
        else:
            self.list_orientations()

    def get_score(self):
        if self.refine.Umat is not None:
            self.score = self.refine.score()
            self.result_textbox.setText('%s peaks; Score: %.4f'
                                        % (len(self.refine.idx), self.score))

    def list_orientations(self):
        message_box = BaseDialog(self)
        message_box.setMinimumWidth(600)
        message_box.setMinimumHeight(600)
        header = ['i', 'x', 'y', 'z', 'Polar', 'Azi', 'Intensity',
                  'H', 'K', 'L', 'Diff']
        peak_list = self.refine.get_peaks()
        self.refine.assign_rings()
        self.rings = self.refine.get_ring_hkls()
        orient_layout = QtWidgets.QHBoxLayout()
        if self.refine.primary is None:
            self.refine.primary = 0
        if self.refine.secondary is None:
            self.refine.secondary = 1
        self.primary_box = QtWidgets.QLineEdit(str(self.refine.primary))
        self.primary_box.setAlignment(QtCore.Qt.AlignRight)
        self.primary_box.setFixedWidth(80)
        self.secondary_box = QtWidgets.QLineEdit(str(self.refine.secondary))
        self.secondary_box.setAlignment(QtCore.Qt.AlignRight)
        self.secondary_box.setFixedWidth(80)
        orient_button = QtWidgets.QPushButton('Orient')
        orient_button.clicked.connect(self.orient)
        refine_button = QtWidgets.QPushButton('Refine')
        refine_button.clicked.connect(self.refine_orientation)
        restore_button = QtWidgets.QPushButton('Restore')
        restore_button.clicked.connect(self.restore_orientation)
        orient_layout.addStretch()
        orient_layout.addWidget(QtWidgets.QLabel('Primary'))
        orient_layout.addWidget(self.primary_box)
        orient_layout.addWidget(QtWidgets.QLabel('Secondary'))
        orient_layout.addWidget(self.secondary_box)
        orient_layout.addStretch()
        orient_layout.addWidget(orient_button)     
        orient_layout.addWidget(refine_button)
        orient_layout.addWidget(restore_button)

        grid = QtWidgets.QGridLayout()
        grid.setSpacing(10)
        self.lattice = GridParameters()
        self.lattice.add('a', self.refine.a, 'a', False)
        self.lattice.add('b', self.refine.b, 'b', False)
        self.lattice.add('c', self.refine.c, 'c', False)
        self.lattice.add('alpha', self.refine.alpha, 'alpha', False)
        self.lattice.add('beta', self.refine.beta, 'beta', False)
        self.lattice.add('gamma', self.refine.gamma, 'gamma', False)
        p = self.lattice['a']
        p.box.setFixedWidth(80)
        label, value, checkbox = p.label, p.value, p.vary
        grid.addWidget(p.label, 0, 0, QtCore.Qt.AlignRight)
        grid.addWidget(p.box, 0, 1, QtCore.Qt.AlignHCenter)
        grid.addWidget(p.checkbox, 0, 2, QtCore.Qt.AlignHCenter)
        p = self.lattice['b']
        p.box.setFixedWidth(80)
        label, value, checkbox = p.label, p.value, p.vary
        grid.addWidget(p.label, 0, 3, QtCore.Qt.AlignRight)
        grid.addWidget(p.box, 0, 4, QtCore.Qt.AlignHCenter)
        grid.addWidget(p.checkbox, 0, 5, QtCore.Qt.AlignHCenter)
        p = self.lattice['c']
        p.box.setFixedWidth(80)
        label, value, checkbox = p.label, p.value, p.vary
        grid.addWidget(p.label, 0, 6, QtCore.Qt.AlignRight)
        grid.addWidget(p.box, 0, 7, QtCore.Qt.AlignHCenter)
        grid.addWidget(p.checkbox, 0, 8, QtCore.Qt.AlignHCenter)
        p = self.lattice['alpha']
        p.box.setFixedWidth(80)
        label, value, checkbox = p.label, p.value, p.vary
        grid.addWidget(p.label, 1, 0, QtCore.Qt.AlignRight)
        grid.addWidget(p.box, 1, 1, QtCore.Qt.AlignHCenter)
        grid.addWidget(p.checkbox, 1, 2, QtCore.Qt.AlignHCenter)
        p = self.lattice['beta']
        p.box.setFixedWidth(80)
        label, value, checkbox = p.label, p.value, p.vary
        grid.addWidget(p.label, 1, 3, QtCore.Qt.AlignRight)
        grid.addWidget(p.box, 1, 4, QtCore.Qt.AlignHCenter)
        grid.addWidget(p.checkbox, 1, 5, QtCore.Qt.AlignHCenter)
        p = self.lattice['gamma']
        p.box.setFixedWidth(80)
        label, value, checkbox = p.label, p.value, p.vary
        grid.addWidget(p.label, 1, 6, QtCore.Qt.AlignRight)
        grid.addWidget(p.box, 1, 7, QtCore.Qt.AlignHCenter)
        grid.addWidget(p.checkbox, 1, 8, QtCore.Qt.AlignHCenter)
        self.table_view = QtWidgets.QTableView()
        self.table_model = NXTableModel(self, peak_list, header)
        self.table_view.setModel(self.table_model)
        self.table_view.resizeColumnsToContents()
        self.table_view.horizontalHeader().stretchLastSection()
        self.table_view.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.table_view.doubleClicked.connect(self.plot_peak)
        self.table_view.setSortingEnabled(True)
        self.table_view.sortByColumn(0, QtCore.Qt.AscendingOrder)
        layout = QtWidgets.QVBoxLayout()
        layout.addLayout(orient_layout)
        layout.addLayout(grid)
        layout.addWidget(self.table_view)
        close_layout = QtWidgets.QHBoxLayout()
        self.status_text = QtWidgets.QLabel('Score: %.4f' % self.refine.score())
        self.tolerance_box = QtWidgets.QLineEdit(str(self.refine.hkl_tolerance))
        self.tolerance_box.setAlignment(QtCore.Qt.AlignRight)
        self.tolerance_box.setMaxLength(5)
        self.tolerance_box.editingFinished.connect(self.update_table)
        self.tolerance_box.setFixedWidth(80)
        save_button = QtWidgets.QPushButton('Save Orientation')
        save_button.clicked.connect(self.save_orientation)
        close_button = QtWidgets.QPushButton('Close Window')
        close_button.clicked.connect(message_box.close)
        close_layout.addWidget(self.status_text)
        close_layout.addStretch()
        close_layout.addWidget(QtWidgets.QLabel('Threshold'))
        close_layout.addWidget(self.tolerance_box)
        close_layout.addStretch()
        close_layout.addWidget(save_button)
        close_layout.addStretch()
        close_layout.addWidget(close_button)
        layout.addLayout(close_layout)
        message_box.setLayout(layout)
        message_box.setWindowTitle('%s Peak Table' % self.entry.nxtitle)
        message_box.adjustSize()
        message_box.show()
        self.plotview = None

    def plot_peak(self):
        row = self.table_view.currentIndex().row()
        data = self.entry.data
        x, y, z = [self.table_view.model().peak_list[row][i] for i in range(1, 4)]
        xmin, xmax = max(0,x-200), min(x+200,data.nxsignal.shape[2])
        ymin, ymax = max(0,y-200), min(y+200,data.nxsignal.shape[1])
        zmin, zmax = max(0,z-200), min(z+200,data.nxsignal.shape[0])
        zslab=np.s_[z,ymin:ymax,xmin:xmax]
        if self.plotview is None:
            self.plotview = NXPlotView('X-Y Projection')
        self.plotview.plot(data[zslab], log=True)
        self.plotview.crosshairs(x, y)

    def orient(self):
        self.refine.primary = int(self.primary_box.text())
        self.refine.secondary = int(self.secondary_box.text())
        self.refine.Umat = self.refine.get_UBmat(self.refine.primary, 
                                                 self.refine.secondary) \
                           * self.refine.Bimat
        self.update_table()

    def refine_orientation(self):
        idx = self.refine.idx
        intensities = self.refine.intensity[idx]
        sigma = np.average(intensities) / intensities
        p0 = self.set_parameters(idx)
        def diffs(p):
            self.get_parameters(p)
            UBimat = np.linalg.inv(self.refine.UBmat)
            Q = [UBimat * self.Gvec[i] for i in idx]
            dQ = Q - np.rint(Q)
            return np.array([np.linalg.norm(self.refine.Bmat*np.matrix(dQ[i])) 
                             for i in idx]) / sigma
        popt, C, info, msg, success = leastsq(diffs, p0, full_output=1)
        self.get_parameters(popt)
        self.update_lattice()
        self.update_table()
        self.status_text.setText('Score: %.4f' % self.refine.score())

    def restore_orientation(self):
        self.refine.Umat = self.Umat
        for par in self.lattice.values():
            par.value = par.init_value
        self.update_table()

    def update_table(self):
        self.refine.hkl_tolerance = np.float32(self.tolerance_box.text())
        self.table_model.peak_list = self.refine.get_peaks()
        rows, columns = len(self.table_model.peak_list), 11
        self.table_model.dataChanged.emit(self.table_model.createIndex(0, 0),
                                          self.table_model.createIndex(rows-1, columns-1))
        self.status_text.setText('Score: %.4f' % self.refine.score())

    def update_lattice(self):
        self.lattice['a'].value = self.refine.a
        self.lattice['b'].value = self.refine.b
        self.lattice['c'].value = self.refine.c
        self.lattice['alpha'].value = self.refine.alpha
        self.lattice['beta'].value = self.refine.beta
        self.lattice['gamma'].value = self.refine.gamma

    def set_parameters(self, idx):
        x, y, z = self.refine.xp[idx], self.refine.yp[idx], self.refine.zp[idx]
        self.Gvec = [self.refine.Gvec(xx,yy,zz) for xx,yy,zz in zip(x,y,z)]
        self.Umat = self.refine.Umat
        pars = []
        for par in self.lattice.values():
            par.init_value = par.value
            if par.vary:
                pars.append(par.value)
        p0 = np.zeros(shape=(len(pars)+9), dtype=np.float32)
        p0[:len(pars)] = pars
        p0[len(pars):] = np.ravel(self.refine.Umat)
        return p0

    def get_parameters(self, p):
        i = 0
        for par in self.lattice.values():
            if par.vary:
                par.value = p[i]
                i += 1
        self.refine.a, self.refine.b, self.refine.c, \
            self.refine.alpha, self.refine.beta, self.refine.gamma = \
                [par.value for par in self.lattice.values()]
        self.refine.set_symmetry()
        self.refine.Umat = np.matrix(p[i:]).reshape(3,3)

    def save_orientation(self):
        self.write_parameters()

    def write_parameters(self):
        try:
            self.refine.write_parameters()
        except NeXusError as error:
            report_error('Defining Orientation', error)


class NXTableModel(QtCore.QAbstractTableModel):

    def __init__(self, parent, peak_list, header, *args):
        super(NXTableModel, self).__init__(parent, *args)
        self.peak_list = peak_list
        self.header = header
        self.parent = parent

    def rowCount(self, parent):
        return len(self.peak_list)

    def columnCount(self, parent):
        return len(self.peak_list[0])

    def data(self, index, role):
        if not index.isValid():
             return None
        elif role == QtCore.Qt.ToolTipRole:
            row, col = index.row(), index.column()
            peak = self.peak_list[row][0]
            return str(self.parent.rings[self.parent.refine.rp[peak]])
        elif role == QtCore.Qt.DisplayRole:
            row, col = index.row(), index.column()
            value = self.peak_list[row][col]
            if col < 4:
                return str(value)
            elif col == 6:
                return "%5.3g" % value
            elif col == 10:
                return "%.3f" % value
            else:
                return "%.2f" % value
        elif role == QtCore.Qt.TextAlignmentRole:
            return int(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        elif role == QtCore.Qt.BackgroundRole:
            row, col = index.row(), index.column()
            peak = self.peak_list[row][0]
            if peak == self.parent.refine.primary or \
                 peak == self.parent.refine.secondary:
                return QtGui.QColor(QtCore.Qt.lightGray)
            elif self.peak_list[row][10] > self.parent.refine.hkl_tolerance:
                return QtGui.QColor(QtCore.Qt.red)
            else:
                return None
            
        return None

    def headerData(self, col, orientation, role):
        if (orientation == QtCore.Qt.Horizontal and 
            role == QtCore.Qt.DisplayRole):
            return self.header[col]
        return None

    def sort(self, col, order):
        """sort table by given column number col"""
        self.layoutAboutToBeChanged.emit()
        self.peak_list = sorted(self.peak_list, key=operator.itemgetter(col))
        if order == QtCore.Qt.DescendingOrder:
            self.peak_list.reverse()
        self.layoutChanged.emit()
