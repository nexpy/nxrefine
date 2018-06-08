from nexpy.gui.pyqt import QtCore, QtWidgets 
import numpy as np
from nexpy.gui.datadialogs import BaseDialog, GridParameters
from nexpy.gui.utils import report_error
from nexusformat.nexus import NeXusError, NXfield
from nxrefine.nxreduce import Lock, LockException, NXReduce


def show_dialog():
    try:
        dialog = MaximumDialog()
        dialog.show()
    except NeXusError as error:
        report_error("Finding Maximum", error)
        

class MaximumDialog(BaseDialog):

    def __init__(self, parent=None):
        super(MaximumDialog, self).__init__(parent)

        self.select_entry(self.choose_entry)

        self.parameters = GridParameters()
        self.parameters.add('first', '', 'First Frame')
        self.parameters.add('last', '', 'Last Frame')

        self.output = QtWidgets.QLabel('Maximum Value:')
        self.set_layout(self.entry_layout, self.output,
                        self.parameters.grid(),
                        self.action_buttons(('Find Maximum', self.find_maximum)),
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
        self.output.setText('Maximum Value: %s' % value)

    def find_maximum(self):
        self.check_lock(self.reduce.data_file)
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

    def check_lock(self, file_name):
        try:
            with Lock(file_name, timeout=2):
                pass
        except LockException as error:
            if self.confirm_action('Clear lock?', str(error)):
                Lock(file_name).release()

    def get_maximum(self, maximum):
        self.maximum = maximum

    def stop(self):
        self.stop_progress()
        if self.thread and self.thread.isRunning():
            self.reduce.stopped = True
        self.stop_thread()

    def accept(self):
        try:
            with Lock(self.reduce.wrapper_file):
                self.reduce.write_maximum(self.maximum)
        except LockException as error:
            if self.confirm_action('Clear lock?', str(error)):
                Lock(self.reduce.wrapper_file).release()
        self.stop()
        super(MaximumDialog, self).accept()

    def reject(self):
        self.stop()
        super(MaximumDialog, self).reject()
