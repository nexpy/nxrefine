# -----------------------------------------------------------------------------
# Copyright (c) 2015-2021, NeXpy Development Team.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file COPYING, distributed with this software.
# -----------------------------------------------------------------------------
import operator

import numpy as np
from nexpy.gui.datadialogs import GridParameters, NXDialog
from nexpy.gui.plotview import NXPlotView
from nexpy.gui.pyqt import QtCore, QtWidgets
from nexpy.gui.utils import is_file_locked, report_error
from nexpy.gui.widgets import NXLabel, NXPushButton
from nexusformat.nexus import NeXusError, NXLock
from nxrefine.nxreduce import NXReduce
from nxrefine.nxrefine import NXRefine
from nxrefine.nxsettings import NXSettings


def show_dialog():
    try:
        dialog = FindDialog()
        dialog.show()
    except NeXusError as error:
        report_error("Finding Peaks", error)


class FindDialog(NXDialog):

    def __init__(self, parent=None):
        super().__init__(parent)

        self.select_entry(self.choose_entry)

        default = NXSettings().settings['nxreduce']
        self.parameters = GridParameters()
        self.parameters.add('threshold', default['threshold'], 'Threshold')
        self.parameters.add('first', default['first'], 'First Frame')
        self.parameters.add('last', default['last'], 'Last Frame')
        self.parameters.add('min_pixels', default['min_pixels'],
                            'Minimum Pixels in Peak')
        self.parameters.grid()
        self.find_button = NXPushButton('Find Peaks', self.find_peaks)
        self.peak_count = NXLabel()
        self.peak_count.setVisible(False)
        self.find_layout = self.make_layout(
            self.action_buttons(('Find Peaks', self.find_peaks),
                                ('List Peaks', self.list_peaks)),
            self.peak_count, align='center')
        self.set_layout(self.entry_layout,
                        self.progress_layout(save=True))
        self.progress_bar.setVisible(False)
        self.progress_bar.setValue(0)
        self.set_title('Find Peaks')
        self.reduce = None
        self.refine = None
        self.peaks_box = None

    def choose_entry(self):
        if self.layout.count() == 2:
            self.insert_layout(1, self.parameters.grid_layout)
            self.insert_layout(2, self.find_layout)
        self.reduce = NXReduce(self.entry)
        self.refine = NXRefine(self.entry)
        self.refine.polar_max = self.refine.two_theta_max()
        if self.reduce.first is not None:
            self.parameters['first'].value = self.reduce.first
        if self.reduce.last:
            self.parameters['last'].value = self.reduce.last
        else:
            try:
                self.parameters['last'].value = self.reduce.shape[0]
            except Exception:
                pass
        self.parameters['threshold'].value = self.reduce.threshold

    @property
    def threshold(self):
        try:
            return int(self.parameters['threshold'].value)
        except Exception as error:
            report_error("Finding Peaks", str(error))

    @property
    def first(self):
        try:
            return int(self.parameters['first'].value)
        except Exception as error:
            report_error("Finding Peaks", str(error))

    @property
    def last(self):
        try:
            return int(self.parameters['last'].value)
        except Exception as error:
            report_error("Finding Peaks", str(error))

    @property
    def min_pixels(self):
        try:
            return int(self.parameters['min_pixels'].value)
        except Exception as error:
            report_error("Finding Peaks", str(error))

    def find_peaks(self):
        if is_file_locked(self.reduce.data_file):
            if self.confirm_action('Clear lock?',
                                   f'{self.reduce.data_file} is locked'):
                NXLock(self.reduce.data_file).release()
            else:
                return
        self.start_thread()
        self.reduce = NXReduce(self.entry, threshold=self.threshold,
                               first=self.first, last=self.last,
                               min_pixels=self.min_pixels,
                               find=True, overwrite=True, gui=True)
        self.reduce.moveToThread(self.thread)
        self.reduce.start.connect(self.start_progress)
        self.reduce.update.connect(self.update_progress)
        self.reduce.result.connect(self.get_peaks)
        self.reduce.stop.connect(self.stop)
        self.thread.started.connect(self.reduce.nxfind)
        self.thread.start(QtCore.QThread.LowestPriority)

    def get_peaks(self, peaks):
        self.peaks = peaks
        self.peak_count.setText(f'{len(self.peaks)} peaks found')
        self.peak_count.setVisible(True)
        self.refine.xp = np.array([peak.x for peak in peaks])
        self.refine.yp = np.array([peak.y for peak in peaks])
        self.refine.zp = np.array([peak.z for peak in peaks])
        self.refine.intensity = np.array([peak.intensity for peak in peaks])
        self.refine.polar_angle, self.refine.azimuthal_angle = (
            self.refine.calculate_angles(self.refine.xp, self.refine.yp))
        self.update_table()

    def stop(self):
        self.stop_progress()
        if self.thread and self.thread.isRunning():
            self.reduce.stopped = True
        self.stop_thread()

    def list_peaks(self):
        if self.peaks_box in self.mainwindow.dialogs:
            self.update_table()
            return
        self.peaks_box = NXDialog(self)
        self.peaks_box.setMinimumWidth(600)
        self.peaks_box.setMinimumHeight(600)
        header = ['i', 'x', 'y', 'z', 'Polar', 'Azi', 'Intensity',
                  'H', 'K', 'L', 'Diff']
        peak_list = self.refine.get_peaks()
        self.table_view = QtWidgets.QTableView()
        self.table_model = NXTableModel(self, peak_list, header)
        self.table_view.setModel(self.table_model)
        self.table_view.resizeColumnsToContents()
        self.table_view.horizontalHeader().stretchLastSection()
        self.table_view.setSelectionBehavior(
            QtWidgets.QAbstractItemView.SelectRows)
        self.table_view.doubleClicked.connect(self.plot_peak)
        self.table_view.setSortingEnabled(True)
        self.table_view.sortByColumn(0, QtCore.Qt.AscendingOrder)
        self.peaks_box.set_layout(self.table_view,
                                  self.close_buttons(close=True))
        self.peaks_box.set_title(f'{self.refine.name} Peak Table')
        self.peaks_box.adjustSize()
        self.peaks_box.show()
        self.plotview = None

    def update_table(self):
        if self.peaks_box not in self.mainwindow.dialogs:
            return
        elif self.table_model is None:
            self.close_peaks_box()
            self.list_peaks()
        self.table_model.peak_list = self.refine.get_peaks()
        rows, columns = len(self.table_model.peak_list), 11
        self.table_model.dataChanged.emit(
            self.table_model.createIndex(0, 0),
            self.table_model.createIndex(rows - 1, columns - 1))
        self.table_view.resizeColumnsToContents()
        self.peaks_box.set_title(f'{self.refine.name} Peak Table')
        self.peaks_box.adjustSize()
        self.peaks_box.setVisible(True)

    def plot_peak(self):
        row = self.table_view.currentIndex().row()
        data = self.entry.data
        i, x, y, z = [self.table_view.model().peak_list[row][i]
                      for i in range(4)]
        signal = data.nxsignal
        xmin, xmax = max(0, x-200), min(x+200, signal.shape[2])
        ymin, ymax = max(0, y-200), min(y+200, signal.shape[1])
        zmin, zmax = max(0, z-20), min(z+20, signal.shape[0])
        zslab = np.s_[zmin:zmax, ymin:ymax, xmin:xmax]
        if 'Peak Plot' in self.plotviews:
            self.plotview = self.plotviews['Peak Plot']
        else:
            self.plotview = NXPlotView('Peak Plot')
        self.plotview.plot(data[zslab], log=True)
        self.plotview.ax.set_title(f'{data.nxtitle}: Peak {i}')
        self.plotview.ztab.maxbox.setValue(z)
        self.plotview.aspect = 'equal'
        self.plotview.crosshairs(x, y, color='r', linewidth=0.5)

    def close_peaks_box(self):
        try:
            self.peaks_box.close()
        except Exception:
            pass
        self.peaks_box = None

    def accept(self):
        try:
            self.reduce.write_peaks(self.peaks)
            self.reduce.record('nxfind', threshold=self.threshold,
                               first_frame=self.first, last_frame=self.last,
                               min_pixels=self.min_pixels,
                               peak_number=len(self.peaks))
            self.reduce.record_end('nxfind')
            super().accept()
        except Exception as error:
            report_error("Finding Peaks", str(error))

    def reject(self):
        self.stop()
        super().reject()


class NXTableModel(QtCore.QAbstractTableModel):

    def __init__(self, parent, peak_list, header, *args):
        super().__init__(parent, *args)
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
                return f"{value:5.3g}"
            elif col == 10:
                return f"{value:.3f}"
            else:
                return f"{value:.2f}"
        elif role == QtCore.Qt.TextAlignmentRole:
            return int(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
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
