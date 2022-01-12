# -----------------------------------------------------------------------------
# Copyright (c) 2015-2021, NeXpy Development Team.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file COPYING, distributed with this software.
# -----------------------------------------------------------------------------

from nexpy.gui.datadialogs import GridParameters, NXDialog
from nexpy.gui.pyqt import QtCore
from nexpy.gui.utils import is_file_locked, report_error
from nexpy.gui.widgets import NXLabel, NXPushButton
from nexusformat.nexus import NeXusError, NXLock, NXLockException
from nxrefine.nxreduce import NXReduce


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

        self.parameters = GridParameters()
        self.parameters.add('threshold', '', 'Threshold')
        self.parameters.add('first', '', 'First Frame')
        self.parameters.add('last', '', 'Last Frame')
        self.find_button = NXPushButton('Find Peaks', self.find_peaks)
        self.peak_count = NXLabel()
        self.peak_count.setVisible(False)
        find_layout = self.make_layout(self.find_button, self.peak_count,
                                       align='center')
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
        if self.reduce.first is not None:
            self.parameters['first'].value = self.reduce.first
        if self.reduce.last:
            self.parameters['last'].value = self.reduce.last
        else:
            try:
                self.parameters['last'].value = len(self.entry.data.nxaxes[0])
            except Exception:
                pass
        if self.reduce.threshold:
            self.parameters['threshold'].value = self.reduce.threshold

    @property
    def threshold(self):
        try:
            _threshold = int(self.parameters['threshold'].value)
            if _threshold > 0.0:
                return _threshold
            else:
                return None
        except Exception:
            return None

    @property
    def first(self):
        try:
            _first = int(self.parameters['first'].value)
            if _first >= 0:
                return _first
            else:
                return None
        except Exception as error:
            return None

    @property
    def last(self):
        try:
            _last = int(self.parameters['last'].value)
            if _last > 0:
                return _last
            else:
                return None
        except Exception as error:
            return None

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

    def stop(self):
        self.stop_progress()
        if self.thread and self.thread.isRunning():
            self.reduce.stopped = True
        self.stop_thread()

    def accept(self):
        try:
            self.reduce.write_peaks(self.peaks)
            self.reduce.record('nxfind', threshold=self.threshold,
                               first_frame=self.first, last_frame=self.last,
                               peak_number=len(self.peaks))
            self.reduce.record_end('nxfind')
            super().accept()
        except Exception as error:
            report_error("Finding Peaks", str(error))

    def reject(self):
        self.stop()
        super().reject()
