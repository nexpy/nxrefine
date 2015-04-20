import operator
from PySide import QtCore, QtGui
import numpy as np
import random
from scipy.optimize import minimize
from nexpy.gui.datadialogs import BaseDialog, GridParameters
from nexpy.gui.mainwindow import report_error
from nexpy.gui.plotview import NXPlotView
from nexusformat.nexus import NeXusError
from nxpeaks.nxrefine import NXRefine


def show_dialog(parent=None):
    try:
        dialog = OrientationDialog(parent)
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
        self.parameters.add('omega_start', self.refine.omega_start, 'Omega Start (deg)')
        self.parameters.add('omega_step', self.refine.omega_step, 'Omega Step (deg)')
        self.parameters.add('polar', self.refine.polar_max, 'Max. Polar Angle (deg)')
        self.parameters.add('polar_tolerance', self.refine.polar_tolerance, 'Polar Angle Tolerance')
        self.parameters.add('peak_tolerance', self.refine.peak_tolerance, 'Peak Angle Tolerance')
        self.parameters.add('hkl_tolerance', self.refine.hkl_tolerance, 'HKL Tolerance')
        action_buttons = self.action_buttons(
                             ('Generate Grains', self.generate_grains),
                             ('List Peaks', self.list_peaks))
        self.grain_layout = QtGui.QHBoxLayout()
        self.grain_combo = QtGui.QComboBox()
        self.grain_combo.setSizeAdjustPolicy(QtGui.QComboBox.AdjustToContents)
        self.grain_combo.currentIndexChanged.connect(self.set_grain)
        self.grain_textbox = QtGui.QLabel()
        self.grain_layout.addWidget(self.grain_combo)
        self.grain_layout.addStretch()
        self.grain_layout.addWidget(self.grain_textbox)
        bottom_layout = QtGui.QHBoxLayout()
        self.result_textbox = QtGui.QLabel()
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
        self.parameters['omega_start'].value = self.refine.omega_start
        self.parameters['omega_step'].value = self.refine.omega_step
        self.parameters['polar'].value = self.refine.polar_max
        self.parameters['polar_tolerance'].value = self.refine.polar_tolerance
        self.parameters['peak_tolerance'].value = self.refine.peak_tolerance
        self.parameters['hkl_tolerance'].value = self.refine.hkl_tolerance

    def get_omega(self):
        return (self.parameters['omega_start'].value,
                self.parameters['omega_step'].value) 

    def set_omega(self):
        self.refine.omega_start, self.refine.omega_step = self.get_omega() 

    @property
    def polar_max(self):
        return self.parameters['polar'].value

    def set_polar_max(self):
        self.refine.set_polar_max(self.polar_max)

    def get_polar_tolerance(self):
        return self.parameters['polar_tolerance'].value

    def set_polar_tolerance(self):
        self.refine.polar_tolerance = self.get_polar_tolerance()

    def get_peak_tolerance(self):
        return self.parameters['peak_tolerance'].value

    def set_peak_tolerance(self):
        self.refine.peak_tolerance = self.get_peak_tolerance()

    def get_hkl_tolerance(self):
        return self.parameters['hkl_tolerance'].value

    def set_hkl_tolerance(self):
        self.refine.hkl_tolerance = self.get_hkl_tolerance()

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
        self.refine.omega_start, self.refine.omega_step = self.get_omega()
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
        orient_layout = QtGui.QHBoxLayout()
        if self.refine.primary is None:
            self.refine.primary = 0
        if self.refine.secondary is None:
            self.refine.secondary = 1
        self.primary_box = QtGui.QLineEdit(str(self.refine.primary))
        self.secondary_box = QtGui.QLineEdit(str(self.refine.secondary))
        orient_button = QtGui.QPushButton('Orient')
        orient_button.clicked.connect(self.orient)
        refine_button = QtGui.QPushButton('Refine')
        refine_button.clicked.connect(self.refine_orientation)
        orient_layout.addStretch()
        orient_layout.addWidget(QtGui.QLabel('Primary'))
        orient_layout.addWidget(self.primary_box)
        orient_layout.addWidget(QtGui.QLabel('Secondary'))
        orient_layout.addWidget(self.secondary_box)
        orient_layout.addStretch()
        orient_layout.addWidget(orient_button)     
        orient_layout.addWidget(refine_button)   
        self.table_view = QtGui.QTableView()
        self.table_model = NXTableModel(self, peak_list, header)
        self.table_view.setModel(self.table_model)
        self.table_view.resizeColumnsToContents()
        self.table_view.horizontalHeader().stretchLastSection()
        self.table_view.setSelectionBehavior(QtGui.QAbstractItemView.SelectRows)
        self.table_view.doubleClicked.connect(self.plot_peak)
        self.table_view.setSortingEnabled(True)
        self.table_view.sortByColumn(0, QtCore.Qt.AscendingOrder)
        layout = QtGui.QVBoxLayout()
        layout.addLayout(orient_layout)
        layout.addWidget(self.table_view)
        close_layout = QtGui.QHBoxLayout()
        self.status_text = QtGui.QLabel('Score: %.4f' % self.refine.score())
        save_button = QtGui.QPushButton('Save Orientation')
        save_button.clicked.connect(self.save_orientation)
        close_button = QtGui.QPushButton('Close Window')
        close_button.clicked.connect(message_box.close)
        close_layout.addWidget(self.status_text)
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
        self.orient()
        idx = self.refine.idx
        random.shuffle(idx)
        self.idx = idx[0:20]
        p0 = np.zeros(shape=(12), dtype=np.float32)
        p0[0:3] = self.refine.a, self.refine.b, self.refine.c
        p0[3:] = np.ravel(self.refine.Umat)
        self.fit_intensity = self.refine.intensity[self.idx]
        result = minimize(self.residuals, p0, method='nelder-mead',
                          options={'xtol': 1e-5, 'disp': True})
        self.refine.a, self.refine.b, self.refine.c = result.x[0:3]
        self.refine.Umat = np.matrix(result.x[3:]).reshape(3,3)
        self.update_table()
        self.status_text.setText('Score: %.4f' % self.refine.score())

    def update_table(self):
        self.table_model.peak_list = self.refine.get_peaks()
        rows, columns = len(self.table_model.peak_list), 11
        self.table_model.dataChanged.emit(self.table_model.createIndex(0, 0),
                                          self.table_model.createIndex(rows-1, columns-1))
        self.status_text.setText('Score: %.4f' % self.refine.score())

    def residuals(self, p):
        self.refine.a, self.refine.b, self.refine.c = p[0:3]
        self.refine.Umat = np.matrix(p[3:]).reshape(3,3)
        diffs = np.array([self.refine.diff(i) for i in self.idx])
        score = np.sum(diffs * self.fit_intensity)
        return score

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
        if orientation == QtCore.Qt.Horizontal and role == QtCore.Qt.DisplayRole:
            return self.header[col]
        return None

    def sort(self, col, order):
        """sort table by given column number col"""
        self.layoutAboutToBeChanged.emit()
        self.peak_list = sorted(self.peak_list, key=operator.itemgetter(col))
        if order == QtCore.Qt.DescendingOrder:
            self.peak_list.reverse()
        self.layoutChanged.emit()
