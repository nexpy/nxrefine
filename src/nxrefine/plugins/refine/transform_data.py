from nexpy.gui.pyqt import QtGui, QtWidgets
import os
import numpy as np
from nexpy.gui.datadialogs import NXDialog
from nexpy.gui.utils import report_error
from nexpy.gui.widgets import NXLabel, NXLineEdit
from nexusformat.nexus import NeXusError
from nxrefine.nxrefine import NXRefine


def show_dialog():
    try:
        dialog = TransformDialog()
        dialog.show()
    except NeXusError as error:
        report_error("Preparing Data Transform", error)
        

class TransformDialog(NXDialog):

    def __init__(self, parent=None):
        super(TransformDialog, self).__init__(parent)
        
        self.select_entry(self.initialize_grid)
        self.refine = NXRefine()

        grid = QtWidgets.QGridLayout()
        grid.setSpacing(10)
        header_font = QtGui.QFont()
        header_font.setBold(True)
        start_label = NXLabel('Start')
        start_label.setFont(header_font)
        grid.addWidget(start_label, 0, 1)
        step_label = NXLabel('Step')
        step_label.setFont(header_font)
        grid.addWidget(step_label, 0, 2)
        stop_label = NXLabel('Stop')
        stop_label.setFont(header_font)
        grid.addWidget(stop_label, 0, 3)
        grid.addWidget(NXLabel('H:'), 1, 0)
        grid.addWidget(NXLabel('K:'), 2, 0)
        grid.addWidget(NXLabel('L:'), 3, 0)
        self.start_h_box = NXLineEdit()
        self.step_h_box = NXLineEdit()
        self.stop_h_box = NXLineEdit()
        grid.addWidget(self.start_h_box, 1, 1)
        grid.addWidget(self.step_h_box, 1, 2)
        grid.addWidget(self.stop_h_box, 1, 3)
        self.start_k_box = NXLineEdit()
        self.step_k_box = NXLineEdit()
        self.stop_k_box = NXLineEdit()
        grid.addWidget(self.start_k_box, 2, 1)
        grid.addWidget(self.step_k_box, 2, 2)
        grid.addWidget(self.stop_k_box, 2, 3)
        self.start_l_box = NXLineEdit()
        self.step_l_box = NXLineEdit()
        self.stop_l_box = NXLineEdit()
        grid.addWidget(self.start_l_box, 3, 1)
        grid.addWidget(self.step_l_box, 3, 2)
        grid.addWidget(self.stop_l_box, 3, 3)
        self.set_layout(self.entry_layout, grid, 
            self.checkboxes(('copy', 'Copy to all entries', True),
                            ('mask', 'Create masked transform group', True),
                            ('overwrite', 'Overwrite existing transforms', False)),
            self.close_buttons(save=True))
        self.setWindowTitle('Transforming Data')
        try:
            self.initialize_grid()
        except Exception:
            pass

    def get_output_file(self, mask=False, entry=None):
        if entry is None:
            entry = self.entry            
        if mask:
            return os.path.splitext(entry.data.nxsignal.nxfilename)[0]+'_masked_transform.nxs'
        else:
            return os.path.splitext(entry.data.nxsignal.nxfilename)[0]+'_transform.nxs'

    def get_settings_file(self, entry=None):
        if entry is None:
            entry = self.entry            
        return os.path.splitext(entry.data.nxsignal.nxfilename)[0]+'_transform.pars'

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
        self.start_h_box.setText('%g' % self.refine.h_start)
        self.step_h_box.setText('%g' % self.refine.h_step)
        self.stop_h_box.setText('%g' % self.refine.h_stop)
        self.start_k_box.setText('%g' % self.refine.k_start)
        self.step_k_box.setText('%g' % self.refine.k_step)
        self.stop_k_box.setText('%g' % self.refine.k_stop)
        self.start_l_box.setText('%g' % self.refine.l_start)
        self.step_l_box.setText('%g' % self.refine.l_step)
        self.stop_l_box.setText('%g' % self.refine.l_stop)

    def write_parameters(self, output_file, settings_file):
        self.refine.output_file = output_file
        self.refine.settings_file = settings_file
        self.refine.h_start, self.refine.h_step, self.refine.h_stop = self.get_h_grid()
        self.refine.k_start, self.refine.k_step, self.refine.k_stop = self.get_k_grid()
        self.refine.l_start, self.refine.l_step, self.refine.l_stop = self.get_l_grid()
        self.refine.define_grid()

    @property
    def copy(self):
        return self.checkbox['copy'].isChecked()

    @property
    def mask(self):
        return self.checkbox['mask'].isChecked()

    @property
    def overwrite(self):
        return self.checkbox['overwrite'].isChecked()

    def accept(self):
        try:
            if 'transform' in self.entry and not self.overwrite:
                self.display_message('Preparing Transform',
                    'Transform group already exists in %s' % self.entry.nxname)
                return
            if self.mask and 'masked_transform' in self.entry and not self.overwrite:
                self.display_message('Preparing Transform',
                    'Masked transform group already exists in %s' % self.entry.nxname)
                return
            output_file = self.get_output_file()
            settings_file = self.get_settings_file()
            self.write_parameters(output_file, settings_file)
            self.refine.prepare_transform(output_file)
            if self.mask:
                masked_output_file = self.get_output_file(mask=True)
                self.refine.prepare_transform(masked_output_file, mask=True)
            self.refine.write_settings(settings_file)
            if self.copy:
                root = self.entry.nxroot
                for entry in [e for e in root 
                              if e != 'entry' and e != self.entry.nxname]:
                    if 'transform' in root[entry] and not self.overwrite:
                        self.display_message('Preparing Transform',
                            'Transform group already exists in %s' % entry)
                        return
                    if self.mask and 'masked_transform' in root[entry] and not self.overwrite:
                        self.display_message('Preparing Transform',
                            'Masked transform group already exists in %s' % entry)
                        return
                    self.refine = NXRefine(root[entry])
                    output_file = self.get_output_file(entry=root[entry])
                    settings_file = self.get_settings_file(entry=root[entry])
                    self.write_parameters(output_file, settings_file)
                    self.refine.prepare_transform(output_file)
                    if self.mask:
                        masked_output_file = self.get_output_file(mask=True, 
                                                                  entry=root[entry])
                        self.refine.prepare_transform(masked_output_file, mask=True)
                    self.refine.write_settings(settings_file)
                    
            super(TransformDialog, self).accept()
        except NeXusError as error:
            report_error("Preparing Data Transform", error)

