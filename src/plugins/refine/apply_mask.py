from nexpy.gui.pyqt import QtGui
import numpy as np
from nexpy.gui.datadialogs import BaseDialog
from nexpy.gui.mainwindow import report_error
from nexusformat.nexus import NeXusError


def show_dialog():
    dialog = MaskDialog()
    dialog.show()
#    except NeXusError as error:
#        report_error("Applying Mask", error)
        

class MaskDialog(BaseDialog):

    def __init__(self, parent=None):
        super(MaskDialog, self).__init__(parent)
        node = self.get_node()
        self.root = node.nxroot
        self.entry = node.nxentry
        layout = QtGui.QVBoxLayout()
        grid = QtGui.QGridLayout()
        grid.setSpacing(10)
        self.mask_box = QtGui.QLineEdit()
        self.mask_box.setMinimumWidth(300)
        grid.addWidget(QtGui.QLabel('Mask Path:'), 0, 0)
        grid.addWidget(self.mask_box, 0, 1)
        layout.addLayout(grid)
        save_button = QtGui.QPushButton('Save Mask')
        save_button.clicked.connect(self.save_mask)
        layout.addWidget(save_button)
        layout.addWidget(self.close_buttons())
        self.setLayout(layout)
        self.setWindowTitle('Mask Data')
        
        self.mask_box.setText('pilatus_mask/entry/mask')

    def get_mask_path(self):
        return self.mask_box.text()

    def save_mask(self):
        mask = self.treeview.tree[self.get_mask_path()]
        if mask.dtype != np.bool:
            raise NeXusError('Mask must be a Boolean array')
        elif len(mask.shape) == 1:
            raise NeXusError('Mask must be at least two-dimensional')
        elif len(mask.shape) > 2:
            mask = mask[0]                
        self.entry['instrument/detector/pixel_mask'] = mask
        self.entry['instrument/detector/pixel_mask_applied'] = False
#        except NeXusError as error:
#            report_error('Applying Mask', error)
