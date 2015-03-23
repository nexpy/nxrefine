from PySide import QtGui
import numpy as np
from nexpy.gui.datadialogs import BaseDialog
from nexpy.gui.mainwindow import report_error
from nexusformat.nexus import NeXusError, NXfield


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
        self.entry = self.node.nxentry
        if not isinstance(self.node, NXfield):
            raise NeXusError('Node must be an NXfield')
        layout = QtGui.QVBoxLayout()
        self.output = QtGui.QLabel('Maximum Value:')
        self.find_button = QtGui.QPushButton('Find Maximum')
        layout.addWidget(self.output)
        layout.addWidget(self.find_button)
        self.find_button.clicked.connect(self.find_maximum)
        if len(self.node.shape) == 2:
            layout.addWidget(self.buttonbox(save=True))
        elif len(self.node.shape) > 2:
            layout.addLayout(self.progress_layout(save=True))
            self.progress_bar.setVisible(False)
        self.setLayout(layout)
        self.setWindowTitle('Find Maximum Value')

    def find_maximum(self):
        self.maximum = 0.0
        try:
            mask = self.entry['instrument/detector/pixel_mask']
            if len(mask.shape) > 2:
                mask = mask[0]
        except Exception:
            mask = None
        if len(self.node.shape) == 2:
            self.maximum = self.node[:,:].max()
        else:
            self.progress_bar.setVisible(True)
            self.progress_bar.setRange(0, self.node.shape[0])
            chunk_size = self.node.nxfile[self.node.nxpath].chunks[0]
            for i in range(0, self.node.shape[0], chunk_size):
                try:
                    self.progress_bar.setValue(i)
                    self.update_progress()
                    v = self.node[i:i+chunk_size,:,:]
                except IndexError as error:
                    pass
                if mask is not None:
                    v = np.ma.masked_array(v)
                    v.mask = mask
                if self.maximum < v.max():
                    self.maximum = v.max()
            self.progress_bar.setVisible(False)
        self.output.setText('Maximum Value: %s' % self.maximum)

    def accept(self):
        self.node.maximum = self.maximum
        super(MaximumDialog, self).accept()
