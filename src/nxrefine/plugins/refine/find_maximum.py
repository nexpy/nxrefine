from nexpy.gui.pyqt import QtCore, QtWidgets 
import numpy as np
from nexpy.gui.datadialogs import BaseDialog
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

        self.output = QtWidgets.QLabel('Maximum Value:')
        self.set_layout(self.entry_layout, self.output, 
                        self.action_buttons(('Find Maximum', self.find_maximum)),
                        self.checkboxes(('overwrite', 'Overwrite', True)),
                        self.progress_layout(save=True))
        self.progress_bar.setVisible(False)
        self.progress_bar.setValue(0)
        self.set_title('Find Maximum Value')
        self.checkbox['overwrite'].setVisible(False)
        self.reduce = None

    def choose_entry(self):
        self.reduce = NXReduce(self.entry, gui=self)
        self.maximum = self.reduce.maximum
        if self.reduce.not_complete('nxmax'):
            self.checkbox['overwrite'].setVisible(False)
        else:
            self.checkbox['overwrite'].setVisible(True)

    @property
    def maximum(self):
        return np.float(self.output.text().split()[-1])

    @maximum.setter
    def maximum(self, value):
        self.output.setText('Maximum Value: %s' % value)

    def find_maximum(self):
        self.thread = MaximumThread(self.reduce)
        self.thread.update.connect(self.update_progress)
        self.thread.finished.connect(self.get_maximum)
        self.thread.start()

    def get_maximum(self):
        self.maximum = self.thread.maximum

    def accept(self):
        try:
            with Lock(self.reduce.wrapper_file):
                self.reduce.write_maximum(self.maximum)
        except LockException as error:
            if self.confirm_action('Clear lock?', str(error)):
                Lock(self.reduce.wrapper_file).release()
        super(MaximumDialog, self).accept()


class MaximumThread(QtCore.QThread):

    update = QtCore.Signal(object)

    def __init__(self, reduce):
        super(MaximumThread, self).__init__()
        self.reduce = reduce
        self.reduce.update = self.update

    def run(self):
        try:
            with Lock(self.reduce.data_file, timeout=10):
                self.maximum = self.reduce.find_maximum()
        except LockException as error:
            if self.confirm_action('Clear lock?', str(error)):
                Lock(self.reduce.data_file).release()

