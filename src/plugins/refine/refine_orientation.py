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
        dialog = RefineOrientationDialog(parent)
        dialog.show()
    except NeXusError as error:
        report_error("Refining Orientation", error)
        

class RefineOrientationDialog(BaseDialog):

    def __init__(self, parent=None):
        super(RefineOrientationDialog, self).__init__(parent)

        self.select_entry(self.choose_entry)

        self.refine = NXRefine(self.entry)
        self.refine.read_parameters()

        self.parameters = GridParameters()
        self.parameters.add('omega_start', self.refine.omega_start, 'Omega Start (deg)')
        self.parameters.add('omega_step', self.refine.omega_step, 'Omega Step (deg)')
        self.parameters.add('hkl_tolerance', self.refine.hkl_tolerance, 'HKL Tolerance')
        actions = self.action_buttons(('Show Score', self.get_score),
                                      ('List Peaks', self.list_peaks),
                                      ('Refine', self.refine_orientation))
        bottom_layout = QtGui.QHBoxLayout()
        self.result_textbox = QtGui.QLabel()
        bottom_layout.addWidget(self.result_textbox)
        bottom_layout.addStretch()
        bottom_layout.addWidget(self.close_buttons(save=True))
        self.set_layout(self.entry_layout, self.parameters.grid(), actions, bottom_layout)
        self.set_title('Refining Orientation')

        self.Umat = None
        self.idx = None

    def choose_entry(self):
        self.refine = NXRefine(self.entry)
        self.update_parameters()
        self.result_textbox.setText('')

    def update_parameters(self):
        self.parameters['omega_start'].value = self.refine.omega_start
        self.parameters['omega_step'].value = self.refine.omega_step
        self.parameters['hkl_tolerance'].value = self.refine.hkl_tolerance

    def get_omega(self):
        return (self.parameters['omega_start'].value,
                self.parameters['omega_step'].value) 

    def set_omega(self):
        self.refine.omega_start, self.refine.omega_step = self.get_omega() 

    def get_hkl_tolerance(self):
        return self.parameters['hkl_tolerance'].value

    def set_hkl_tolerance(self):
        self.refine.hkl_tolerance = self.get_hkl_tolerance()

    def list_peaks(self):
        self.refine.omega_start, self.refine.omega_step = self.get_omega()
        self.get_score()
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
        self.table_view = QtGui.QTableView()
        self.table_view.setModel(NXTableModel(self, peak_list, header))
        self.table_view.resizeColumnsToContents()
        self.table_view.horizontalHeader().stretchLastSection()
        self.table_view.setSelectionBehavior(QtGui.QAbstractItemView.SelectRows)
        self.table_view.doubleClicked.connect(self.plot_peak)
        self.table_view.setSortingEnabled(True)
        self.table_view.sortByColumn(0, QtCore.Qt.AscendingOrder)
        layout = QtGui.QVBoxLayout()
        layout.addWidget(self.table_view)
        close_layout = QtGui.QHBoxLayout()
        status_text = QtGui.QLabel('Score: %.4f' % self.refine.score())
        close_button = QtGui.QPushButton('Close Window')
        close_button.clicked.connect(message_box.close)
        close_layout.addWidget(status_text)
        close_layout.addStretch()
        close_layout.addWidget(close_button)
        layout.addLayout(close_layout)
        message_box.setLayout(layout)
        s = 'Primary Peak = %s - Secondary Peak = %s' % (self.refine.primary, self.refine.secondary)
        message_box.setWindowTitle(s)
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
        xmin, xmax = max(0,x-200), min(x+200,data.nxsignal.shape[2])
        ymin, ymax = max(0,y-200), min(y+200,data.nxsignal.shape[1])
        zslab=np.s_[z,ymin:ymax,xmin:xmax]
        if self.plotview is None:
            self.plotview = NXPlotView('X-Y Projection')
        self.plotview.plot(data[zslab], log=True)
        self.plotview.crosshairs(x, y)

    def refine_orientation(self):
        idx = self.refine.idx
        random.shuffle(idx)
        self.idx = idx[0:20]
        p0 = np.ravel(self.refine.Umat)
        self.fit_intensity = self.refine.intensity[self.idx]
        result = minimize(self.residuals, p0, method='nelder-mead',
                          options={'xtol': 1e-5, 'disp': True})
        self.Umat = np.matrix(result.x).reshape(3,3)
        self.get_score()

    def residuals(self, p):
        self.refine.Umat = np.matrix(p).reshape(3,3)
        diffs = np.array([self.refine.diff(i) for i in self.idx])
        score = np.sum(diffs * self.fit_intensity)
        return score

    def accept(self):
        self.refine.Umat = self.Umat
        self.write_parameters()
        super(RefineOrientationDialog, self).accept()


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
            if self.peak_list[row][10] > self.parent.refine.hkl_tolerance:
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
