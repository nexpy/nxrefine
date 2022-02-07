# -----------------------------------------------------------------------------
# Copyright (c) 2015-2021, NeXpy Development Team.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file COPYING, distributed with this software.
# -----------------------------------------------------------------------------

import numpy as np
from nexpy.gui.datadialogs import GridParameters, NXDialog
from nexpy.gui.pyqt import QtCore
from nexpy.gui.utils import is_file_locked, report_error
from nexpy.gui.widgets import NXLabel
from nexusformat.nexus import NeXusError, NXLock, NXLockException
from nxrefine.nxreduce import NXReduce


def show_dialog():
    try:
        dialog = MaximumDialog()
        dialog.show()
    except NeXusError as error:
        report_error("Finding Maximum", error)


class MaximumDialog(NXDialog):

    def __init__(self, parent=None):
        super().__init__(parent)

        self.select_entry(self.choose_entry)

        self.parameters = GridParameters()
        self.parameters.add('first', '', 'First Frame')
        self.parameters.add('last', '', 'Last Frame')

        self.output = NXLabel('Maximum Value:')
        self.set_layout(self.entry_layout, self.output,
                        self.parameters.grid(),
                        self.action_buttons(('Find Maximum',
                                             self.find_maximum)),
                        self.progress_layout(save=True))
        self.progress_bar.setVisible(False)
        self.progress_bar.setValue(0)
        self.set_title('Find Maximum Value')
        self.reduce = None

    def choose_entry(self):
        self.reduce = NXReduce(self.entry)
        self.maximum = self.reduce.maximum
        if self.reduce.first:
            self.parameters['first'].value = self.reduce.first
        if self.reduce.last:
            self.parameters['last'].value = self.reduce.last

    @property
    def first(self):
        try:
            _first = np.int32(self.parameters['first'].value)
            if _first >= 0:
                return _first
            else:
                return None
        except Exception as error:
            return None

    @property
    def last(self):
        try:
            _last = np.int32(self.parameters['last'].value)
            if _last > 0:
                return _last
            else:
                return None
        except Exception as error:
            return None

    @property
    def maximum(self):
        return np.float(self.output.text().split()[-1])

    @maximum.setter
    def maximum(self, value):
        self.output.setText(f'Maximum Value: {value}')

    def find_maximum(self):
        if is_file_locked(self.reduce.data_file):
            return
        self.start_thread()
        self.reduce = NXReduce(self.entry, first=self.first, last=self.last,
                               maxcount=True, overwrite=True, gui=True)
        self.reduce.moveToThread(self.thread)
        self.reduce.start.connect(self.start_progress)
        self.reduce.update.connect(self.update_progress)
        self.reduce.result.connect(self.get_maximum)
        self.reduce.stop.connect(self.stop)
        self.thread.started.connect(self.reduce.nxmax)
        self.thread.finished.connect(self.stop)
        self.thread.start(QtCore.QThread.LowestPriority)

    def get_maximum(self, maximum):
        self.maximum = maximum

    def stop(self):
        self.stop_progress()
        if self.thread and self.thread.isRunning():
            self.reduce.stopped = True
        self.stop_thread()

    def accept(self):
        try:
            self.reduce.write_maximum(self.maximum)
            self.reduce.record('nxmax', maximum=self.maximum,
                               first_frame=self.first, last_frame=self.last)
            self.reduce.record_end('nxmax')
            self.stop()
            super().accept()
        except Exception as error:
            report_error("Finding Maximum", error)

    def reject(self):
        self.stop()
        super().reject()
