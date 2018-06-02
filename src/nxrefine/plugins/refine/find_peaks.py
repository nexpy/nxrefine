from nexpy.gui.pyqt import QtCore, QtWidgets
import numpy as np
from nexpy.gui.datadialogs import BaseDialog, GridParameters
from nexpy.gui.utils import report_error
from nexusformat.nexus import *

from nxrefine.nxreduce import Lock, LockException, NXReduce


def show_dialog():
    try:
        dialog = FindDialog()
        dialog.show()
    except NeXusError as error:
        report_error("Finding Peaks", error)


class FindDialog(BaseDialog):

    def __init__(self, parent=None):
        super(FindDialog, self).__init__(parent)

        self.select_entry(self.choose_entry)

        try:
            threshold = np.float32(self.entry.data.attrs['maximum']) / 20
            max_frame = np.int32(len(self.entry.data.nxaxes[0]))
        except Exception:
            threshold = 5000
            max_frame = 0

        self.parameters = GridParameters()
        self.parameters.add('threshold', threshold, 'Threshold')
        self.parameters.add('min', 0, 'First Frame')
        self.parameters.add('max', max_frame, 'Last Frame')
        find_layout = QtWidgets.QHBoxLayout()
        self.find_button = QtWidgets.QPushButton('Find Peaks')
        self.find_button.clicked.connect(self.find_peaks)
        self.peak_count = QtWidgets.QLabel()
        self.peak_count.setVisible(False)
        find_layout.addStretch()
        find_layout.addWidget(self.find_button)
        find_layout.addWidget(self.peak_count)
        find_layout.addStretch()
        self.set_layout(self.entry_layout, 
                        self.parameters.grid(),
                        find_layout,
                        self.progress_layout(save=True))
        self.progress_bar.setVisible(False)
        self.progress_bar.setValue(0)
        self.set_title('Find Peaks')
        self.reduce = None

    def choose_entry(self):
        self.reduce = NXReduce(self.entry)
        try:
            self.parameters['threshold'].value = self.entry['data'].attrs['maximum'] / 10
            self.parameters['max'].value = len(self.entry.data.nxaxes[0])
        except Exception:
            pass

    @property
    def threshold(self):
        return self.parameters['threshold'].value

    @property
    def first(self):
        return np.int32(self.parameters['min'].value)

    @property
    def last(self):
        return np.int32(self.parameters['max'].value)

    def find_peaks(self):
        self.check_lock(self.reduce.data_file)
        self.start_thread()
        self.reduce = NXReduce(self.entry, threshold=self.threshold, 
                               first=self.first, last=self.last,
                               overwrite=True, gui=True)
        self.reduce.moveToThread(self.thread)
        self.reduce.start.connect(self.start_progress)
        self.reduce.update.connect(self.update_progress)
        self.reduce.result.connect(self.get_peaks)
        self.reduce.stop.connect(self.stop)
        self.thread.started.connect(self.reduce.nxfind)
        self.thread.start(QtCore.QThread.LowestPriority)

    def check_lock(self, file_name):
        try:
            with Lock(file_name, timeout=2):
                pass
        except LockException as error:
            if self.confirm_action('Clear lock?', str(error)):
                Lock(file_name).release()

    def get_peaks(self, peaks):
        self.peaks = peaks
        self.peak_count.setText('%s peaks found' % len(self.peaks))
        self.peak_count.setVisible(True)

    def stop(self):
        self.stop_progress()
        if self.thread and self.thread.isRunning():
            self.reduce.stopped = True
        self.stop_thread()

    def accept(self):
        try:
            with Lock(self.reduce.wrapper_file):
                self.reduce.write_peaks(self.peaks)
        except LockException as error:
            if self.confirm_action('Clear lock?', str(error)):
                Lock(self.reduce.wrapper_file).release()
        self.stop()
        super(FindDialog, self).accept()

    def reject(self):
        self.stop()
        super(FindDialog, self).reject()
