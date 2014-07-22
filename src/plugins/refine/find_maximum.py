from PySide import QtGui
import numpy as np
from nexpy.gui.datadialogs import BaseDialog
from nexpy.gui.mainwindow import report_error
from nexpy.api.nexus import NeXusError, NXfield


def show_dialog(parent=None):
    try:
        dialog = MaximumDialog(parent)
        dialog.show()
    except NeXusError as error:
        report_error("Finding Maximum", error)
        

class MaximumDialog(BaseDialog):

    def __init__(self, parent=None):
        super(MaximumDialog, self).__init__(parent)
        self.node = self.get_node()
        if self.node.nxfilemode == 'r':
            raise NeXusError('NeXus file opened as readonly')
        elif not isinstance(self.node, NXfield):
            raise NeXusError('Node must be an NXfield')
        layout = QtGui.QVBoxLayout()
        output_widget = QtGui.QLabel('Maximum Value:')
        layout.addWidget(output_widget)
        if len(self.node.shape) == 2:
            layout.addWidget(self.buttonbox(save=True))
        elif len(self.node.shape) > 2:
            layout.addLayout(self.progress_layout(save=True))
        self.setLayout(layout)
        self.setWindowTitle('Find Maximum Value')
        
        self.maximum = self.find_maximum()
        
        output_widget.setText('Maximum Value: %s' % self.maximum)

    def find_maximum(self):
        maximum = 0.0
        if len(self.node.shape) == 2:
            maximum = self.node[:,:].max()
        else:
            self.progress_bar.setRange(0, self.node.shape[0])
            chunk_size = self.node.nxfile[self.node.nxpath].chunks[0]
            for i in range(0, self.node.shape[0], chunk_size):
                try:
                    self.progress_bar.setValue(i)
                    self.update_progress()
                    v = self.node[i:i+chunk_size,:,:]
                except IndexError as error:
                    pass
                if maximum < v.max():
                    maximum = v.max()
        return maximum

    def accept(self):
        self.node.maximum = self.maximum
        super(MaximumDialog, self).accept()
