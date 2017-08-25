from nexpy.gui.pyqt import QtWidgets 
import numpy as np
from nexpy.gui.datadialogs import BaseDialog
from nexpy.gui.utils import report_error
from nexusformat.nexus import NeXusError, NXfield


def show_dialog():
    try:
        dialog = MaximumDialog()
        dialog.show()
    except Exception as error:
        report_error("Finding Maximum", error)
        

class MaximumDialog(BaseDialog):

    def __init__(self, parent=None):
        super(MaximumDialog, self).__init__(parent)

        self.select_entry(self.choose_entry)

        self.output = QtWidgets.QLabel('Maximum Value:')
        action_buttons = self.action_buttons(('Find Maximum', self.find_maximum))
        self.set_layout(self.entry_layout, self.output, 
                        action_buttons, self.progress_layout(save=True))
        self.progress_bar.setVisible(False)
        self.set_title('Find Maximum Value')

    def choose_entry(self):
        try:
            self.output_maximum(self.entry['data'].attrs['maximum'])
        except Exception:
            self.output_maximum('')

    def output_maximum(self, maximum):
        self.output.setText('Maximum Value: %s' % maximum)

    def find_maximum(self):
        if 'data' not in self.entry:
            raise NeXusError('There must be a group named "data" in the entry')
        self.maximum = 0.0
        try:
            mask = self.entry['instrument/detector/pixel_mask']
            if len(mask.shape) > 2:
                mask = mask[0]
        except Exception:
            mask = None
        signal = self.entry['data'].nxsignal
        if len(signal.shape) == 2:
            self.maximum = signal[:,:].max()
        else:
            self.progress_bar.setVisible(True)
            self.progress_bar.setRange(0, signal.shape[0])
            chunk_size = signal.nxfile[signal.nxpath].chunks[0]
            for i in range(0, signal.shape[0], chunk_size):
                try:
                    self.progress_bar.setValue(i)
                    self.update_progress()
                    v = signal[i:i+chunk_size,:,:]
                except IndexError as error:
                    pass
                if mask is not None:
                    v = np.ma.masked_array(v)
                    v.mask = mask.nxdata
                if self.maximum < v.max():
                    self.maximum = v.max()
            self.progress_bar.setVisible(False)
        self.output_maximum(self.maximum)

    def accept(self):
        self.entry['data'].attrs['maximum'] = self.maximum
        super(MaximumDialog, self).accept()
