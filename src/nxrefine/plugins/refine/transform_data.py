from nexpy.gui.pyqt import QtGui, QtWidgets
import os
import numpy as np
from nexpy.gui.datadialogs import BaseDialog
from nexpy.gui.utils import report_error
from nexusformat.nexus import NeXusError
from nxrefine.nxrefine import NXRefine


def show_dialog():
    try:
        dialog = TransformDialog()
        dialog.show()
    except NeXusError as error:
        report_error("Preparing Data Transform", error)
        

class TransformDialog(BaseDialog):

    def __init__(self, parent=None):
        super(TransformDialog, self).__init__(parent)
        
        self.select_entry(self.initialize_grid)
        self.refine = NXRefine(self.entry)
        self.refine.read_parameters()

        grid = QtWidgets.QGridLayout()
        grid.setSpacing(10)
        header_font = QtGui.QFont()
        header_font.setBold(True)
        start_label = QtWidgets.QLabel('Start')
        start_label.setFont(header_font)
        grid.addWidget(start_label, 0, 1)
        step_label = QtWidgets.QLabel('Step')
        step_label.setFont(header_font)
        grid.addWidget(step_label, 0, 2)
        stop_label = QtWidgets.QLabel('Stop')
        stop_label.setFont(header_font)
        grid.addWidget(stop_label, 0, 3)
        grid.addWidget(QtWidgets.QLabel('H:'), 1, 0)
        grid.addWidget(QtWidgets.QLabel('K:'), 2, 0)
        grid.addWidget(QtWidgets.QLabel('L:'), 3, 0)
        self.start_h_box = QtWidgets.QLineEdit()
        self.step_h_box = QtWidgets.QLineEdit()
        self.stop_h_box = QtWidgets.QLineEdit()
        grid.addWidget(self.start_h_box, 1, 1)
        grid.addWidget(self.step_h_box, 1, 2)
        grid.addWidget(self.stop_h_box, 1, 3)
        self.start_k_box = QtWidgets.QLineEdit()
        self.step_k_box = QtWidgets.QLineEdit()
        self.stop_k_box = QtWidgets.QLineEdit()
        grid.addWidget(self.start_k_box, 2, 1)
        grid.addWidget(self.step_k_box, 2, 2)
        grid.addWidget(self.stop_k_box, 2, 3)
        self.start_l_box = QtWidgets.QLineEdit()
        self.step_l_box = QtWidgets.QLineEdit()
        self.stop_l_box = QtWidgets.QLineEdit()
        grid.addWidget(self.start_l_box, 3, 1)
        grid.addWidget(self.step_l_box, 3, 2)
        grid.addWidget(self.stop_l_box, 3, 3)
        self.set_layout(self.entry_layout, grid, 
            self.checkboxes(('copy', 'Copy to all entries', True),
                            ('overwrite', 'Overwrite existing transforms', False)),
            self.close_buttons(save=True))
        self.setWindowTitle('Transforming Data')
        try:
            self.initialize_grid()
        except Exception:
            pass

    def get_output_file(self):
        return os.path.splitext(self.entry.data.nxsignal.nxfilename)[0]+'_transform.nxs'

    def get_settings_file(self):
        return os.path.splitext(self.entry.data.nxsignal.nxfilename)[0]+'_transform.pars'

    def get_h_grid(self):
        return (np.float32(self.start_h_box.text()),
                np.float32(self.step_h_box.text()),
                np.float32(self.stop_h_box.text()))

    def get_k_grid(self):
        return (np.float32(self.start_k_box.text()),
                np.float32(self.step_k_box.text()),
                np.float32(self.stop_k_box.text()))

    def get_l_grid(self):
        return (np.float32(self.start_l_box.text()),
                np.float32(self.step_l_box.text()),
                np.float32(self.stop_l_box.text()))

    def initialize_grid(self):
        self.refine = NXRefine(self.entry)
        self.refine.initialize_grid()
        self.start_h_box.setText(str(self.refine.h_start))
        self.step_h_box.setText(str(self.refine.h_step))
        self.stop_h_box.setText(str(self.refine.h_stop))
        self.start_k_box.setText(str(self.refine.k_start))
        self.step_k_box.setText(str(self.refine.k_step))
        self.stop_k_box.setText(str(self.refine.k_stop))
        self.start_l_box.setText(str(self.refine.l_start))
        self.step_l_box.setText(str(self.refine.l_step))
        self.stop_l_box.setText(str(self.refine.l_stop))

    def write_parameters(self, output_file, settings_file):
        self.refine.output_file = output_file
        self.refine.settings_file = settings_file
        self.refine.h_start, self.refine.h_step, self.refine.h_stop = self.get_h_grid()
        self.refine.k_start, self.refine.k_step, self.refine.k_stop = self.get_k_grid()
        self.refine.l_start, self.refine.l_step, self.refine.l_stop = self.get_l_grid()
        self.refine.define_grid()

    def accept(self):
        try:
            if ('transform' in self.entry and not
                self.checkbox['overwrite'].isChecked()):
                self.display_message('Preparing Transform',
                    'Transform already exists in %s' % self.entry.nxname)
                return
            output_file = self.get_output_file()
            settings_file = self.get_settings_file()
            self.write_parameters(output_file, settings_file)
            self.refine.prepare_transform(output_file)
            self.refine.write_settings(settings_file)
            if self.checkbox['copy'].isChecked():
                root = self.entry.nxroot
                for entry in [e for e in root 
                              if e != 'entry' and e != self.entry.nxname]:
                    if ('transform' in root[entry] and not
                        self.checkbox['overwrite'].isChecked()):
                        self.display_message('Preparing Transform',
                            'Transform already exists in %s' % entry)
                        return
                    self.refine = NXRefine(root[entry])
                    output = output_file.replace(self.entry.nxname, entry)
                    settings = settings_file.replace(self.entry.nxname, entry)
                    self.write_parameters(output, settings)
                    self.refine.prepare_transform(output)
                    self.refine.write_settings(settings)
                    
            super(TransformDialog, self).accept()
        except NeXusError as error:
            report_error("Preparing Data Transform", error)

