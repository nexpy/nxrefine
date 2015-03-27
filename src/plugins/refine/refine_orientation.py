import operator
from PySide import QtCore, QtGui
import numpy as np
from nexpy.gui.datadialogs import BaseDialog
from nexpy.gui.mainwindow import report_error
from nexpy.gui.plotview import NXPlotView
from nexusformat.nexus import NeXusError
from nxpeaks.nxrefine import NXRefine


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
        self.entry = node.nxentry

        self.layout = QtGui.QVBoxLayout()
        grid = QtGui.QGridLayout()
        grid.setSpacing(10)
        self.start_box = QtGui.QLineEdit('0.0')
        self.start_box.editingFinished.connect(self.set_omega)
        self.step_box = QtGui.QLineEdit('0.1')
        self.step_box.editingFinished.connect(self.set_omega)
        self.polar_box = QtGui.QLineEdit('10.0')
        self.polar_box.editingFinished.connect(self.set_polar_max)
        self.polar_tolerance_box = QtGui.QLineEdit('0.1')
        self.polar_tolerance_box.editingFinished.connect(self.set_polar_tolerance)
        self.peak_tolerance_box = QtGui.QLineEdit('5.0')
        self.peak_tolerance_box.editingFinished.connect(self.set_peak_tolerance)
        grid.addWidget(QtGui.QLabel('Omega Start (deg): '), 0, 0)
        grid.addWidget(QtGui.QLabel('Omega Step (deg):'), 1, 0)
        grid.addWidget(QtGui.QLabel('Max. Polar Angle:'), 2, 0)
        grid.addWidget(QtGui.QLabel('Polar Angle Tolerance:'), 3, 0)
        grid.addWidget(QtGui.QLabel('Peak Angle Tolerance:'), 4, 0)
        grid.addWidget(self.start_box, 0, 1)
        grid.addWidget(self.step_box, 1, 1)
        grid.addWidget(self.polar_box, 2, 1)
        grid.addWidget(self.polar_tolerance_box, 3, 1)
        grid.addWidget(self.peak_tolerance_box, 4, 1)
        self.layout.addLayout(grid)
        grain_layout = QtGui.QHBoxLayout()
        self.grain_button = QtGui.QPushButton('Generate Grains')
        self.grain_button.clicked.connect(self.generate_grains)
        grain_layout.addStretch()
        grain_layout.addWidget(self.grain_button)
        grain_layout.addStretch()
        self.layout.addLayout(grain_layout)
        self.orient_layout = QtGui.QHBoxLayout()
        self.orient_button = QtGui.QPushButton('Orient')
        self.orient_button.clicked.connect(self.orient)
        self.grain_combo = QtGui.QComboBox()
        self.grain_combo.setSizeAdjustPolicy(QtGui.QComboBox.AdjustToContents)
        self.grain_combo.currentIndexChanged.connect(self.set_grain)
        self.grain_textbox = QtGui.QLabel()
        self.refine_button = QtGui.QPushButton('Refine')
        self.refine_button.clicked.connect(self.refine_orientation)
        self.orient_layout.addStretch()
        self.orient_layout.addWidget(self.grain_combo)
        self.orient_layout.addWidget(self.orient_button)
        self.orient_layout.addWidget(self.grain_textbox)      
        self.orient_layout.addWidget(self.refine_button)      
        self.orient_layout.addStretch()
        self.layout.addWidget(self.buttonbox(save=True))
        self.setLayout(self.layout)
        self.setWindowTitle('Refining Orientation')

        self.refine = NXRefine(self.entry)
        self.refine.read_parameters()
        self.set_polar_max()

    def get_omega(self):
        return (np.float32(self.start_box.text()),
                np.float32(self.step_box.text())) 

    def set_omega(self):
        self.refine.omega_start, self.refine.omega_step = self.get_omega() 

    @property
    def polar_max(self):
        return np.float32(self.polar_box.text())

    def set_polar_max(self):
        self.refine.set_polar_max(self.polar_max)

    def get_polar_tolerance(self):
        return np.float32(self.polar_tolerance_box.text())

    def set_polar_tolerance(self):
        self.refine.polar_tolerance = self.get_polar_tolerance()

    def get_peak_tolerance(self):
        return np.float32(self.peak_tolerance_box.text())

    def set_peak_tolerance(self):
        self.refine.peak_tolerance = self.get_peak_tolerance()

    def generate_grains(self):
        self.set_polar_max()
        if self.refine.grains is None:
            self.layout.insertLayout(2, self.orient_layout)
        self.refine.generate_grains()
        self.grain_combo.clear()
        for i in range(len(self.refine.grains)):
            self.grain_combo.addItem('Grain %s' % i)
        self.grain_combo.setCurrentIndex(0)
        self.set_grain()

    def set_grain(self):
        try:
            grain = self.refine.grains[self.get_grain()]
            self.grain_textbox.setText('%s peaks' % len(grain))
            if grain.UBmat:
                self.refine.UBmat = grain.UBmat
        except:
            self.grain_textbox.setText('')

    def get_grain(self):
        return int(self.grain_combo.currentText().split()[-1])

    def orient(self):
        self.refine.omega_start, self.refine.omega_step = self.get_omega()
        grain = self.refine.grains[self.get_grain()]
        self.refine.orient(grain)
        self.refine.UBmat = grain.UBmat
        self.list_orientations(grain)

    def refine_orientation(self):
        self.refine.UBmat = grain.UBmat = self.refine.refine_orientation()
        self.list_orientations(grain)

    def list_orientations(self, grain):
        message_box = BaseDialog(self)
        message_box.setMinimumWidth(600)
        message_box.setMinimumHeight(600)
        self.refine.read_parameters()
        header = ['i', 'x', 'y', 'z', 'Polar', 'Azi', 'Intensity',
                  'H', 'K', 'L', 'Diff']
        peak_list = self.refine.get_peaks()
        self.table_view = QtGui.QTableView()
        self.table_view.setModel(NXTableModel(self, peak_list, header, grain))
        self.table_view.resizeColumnsToContents()
        self.table_view.horizontalHeader().stretchLastSection()
        self.table_view.setSelectionBehavior(QtGui.QAbstractItemView.SelectRows)
        self.table_view.doubleClicked.connect(self.plot_peak)
        self.table_view.setSortingEnabled(True)
        self.table_view.sortByColumn(0, QtCore.Qt.AscendingOrder)
        layout = QtGui.QVBoxLayout()
        layout.addWidget(self.table_view)
        close_layout = QtGui.QHBoxLayout()
        status_text = QtGui.QLabel('Score: %.4f' % self.refine.score(grain, self.polar_max))
        close_button = QtGui.QPushButton('Close Window')
        close_button.clicked.connect(self.accept)
        close_layout.addWidget(status_text)
        close_layout.addStretch()
        close_layout.addWidget(close_button)
        layout.addLayout(close_layout)
        message_box.setLayout(layout)
        s = str(grain)
        message_box.setWindowTitle(s if len(s) <= 50 else s[0:47]+'...')
        message_box.adjustSize()
        message_box.show()
        self.plotview = None

    def write_parameters(self):
        try:
            self.refine.write_parameters()
        except NeXusError as error:
            report_error('Refining Orientation', error)

    def plot_peak(self):
        row = self.table_view.currentIndex().row()
        data = self.entry.data
        x, y, z = [self.table_view.model().peak_list[row][i] for i in range(1, 4)]
        xmin, xmax = max(0,x-200), min(x+200,data.v.shape[2])
        ymin, ymax = max(0,y-200), min(y+200,data.v.shape[1])
        zslab=np.s_[z,ymin:ymax,xmin:xmax]
        if self.plotview is None:
            self.plotview = NXPlotView('X-Y Projection')
        self.plotview.plot(data[zslab], log=True)
        self.plotview.crosshairs(x, y)

    def refine_parameters(self):
        self.initialize_fit()
        p0 = np.array([p.values()[0] for p in self.parameters])
        result = minimize(self.residuals, p0, method='nelder-mead',
                              options={'xtol': 1e-6, 'disp': True})
        self.get_parameters(result.x)
        self.refine.set_symmetry()
        self.update_parameters()

    def refine_orientation(self):    
        p0 = np.ravel(self.refine.UBmat)
        self.fit_intensity = np.array(
            [self.refine.intensity[i] for i in range(self.refine.npks) 
             if self.refine.polar_angle[i] < self.polar_max])
        result = minimize(self.score_orientation, p0, method='nelder-mead',
                              options={'xtol': 1e-6, 'disp': True})
        return np.matrix(result.x).reshape(3,3)

    def score_orientation(self, p):
        self.UBmat = np.matrix(p).reshape(3,3)
        diffs = [self.refine.diff(i) for i in range(self.refine.npks) if 
                 self.refine.polar_angle[i] < self.polar_max]
        return np.sum(diffs * self.fit_intensity)

    def accept(self):
        self.write_parameters()
        super(OrientationDialog, self).accept()


class NXTableModel(QtCore.QAbstractTableModel):

    def __init__(self, parent, peak_list, header, grain, *args):
        super(NXTableModel, self).__init__(parent, *args)
        self.peak_list = peak_list
        self.header = header
        self.grain = grain
        self.parent = parent

    def rowCount(self, parent):
        return len(self.peak_list)

    def columnCount(self, parent):
        return len(self.peak_list[0])

    def data(self, index, role):
        if not index.isValid():
             return None
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
            if peak in self.grain:
                return QtGui.QColor(QtCore.Qt.lightGray)
            elif self.peak_list[row][10] > 0.05:
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
