import os
from PySide import QtGui
import numpy as np
from nexpy.gui.datadialogs import BaseDialog
from nexpy.gui.mainwindow import report_error
from nexpy.api.nexus import NeXusError
from nxrefine import NXRefine


def show_dialog(parent=None):
    try:
        dialog = TransformDialog(parent)
        dialog.show()
    except NeXusError as error:
        report_error("Transforming Data", error)
        

class TransformDialog(BaseDialog):

    def __init__(self, parent=None):
        super(TransformDialog, self).__init__(parent)
        node = self.get_node()
        self.root = node.nxroot
        self.data = self.root['entry/data/v']

        layout = QtGui.QVBoxLayout()
        layout.addLayout(self.settings_box())
        layout.addLayout(self.output_box())
        grid = QtGui.QGridLayout()
        grid.setSpacing(10)
        header_font = QtGui.QFont()
        header_font.setBold(True)
        start_label = QtGui.QLabel('Start')
        start_label.setFont(header_font)
        grid.addWidget(start_label, 0, 1)
        step_label = QtGui.QLabel('Step')
        step_label.setFont(header_font)
        grid.addWidget(step_label, 0, 2)
        stop_label = QtGui.QLabel('Stop')
        stop_label.setFont(header_font)
        grid.addWidget(stop_label, 0, 3)
        grid.addWidget(QtGui.QLabel('H:'), 1, 0)
        grid.addWidget(QtGui.QLabel('K:'), 2, 0)
        grid.addWidget(QtGui.QLabel('L:'), 3, 0)
        self.start_h_box = QtGui.QLineEdit()
        self.step_h_box = QtGui.QLineEdit()
        self.stop_h_box = QtGui.QLineEdit()
        grid.addWidget(self.start_h_box, 1, 1)
        grid.addWidget(self.step_h_box, 1, 2)
        grid.addWidget(self.stop_h_box, 1, 3)
        self.start_k_box = QtGui.QLineEdit()
        self.step_k_box = QtGui.QLineEdit()
        self.stop_k_box = QtGui.QLineEdit()
        grid.addWidget(self.start_k_box, 2, 1)
        grid.addWidget(self.step_k_box, 2, 2)
        grid.addWidget(self.stop_k_box, 2, 3)
        self.start_l_box = QtGui.QLineEdit()
        self.step_l_box = QtGui.QLineEdit()
        self.stop_l_box = QtGui.QLineEdit()
        grid.addWidget(self.start_l_box, 3, 1)
        grid.addWidget(self.step_l_box, 3, 2)
        grid.addWidget(self.stop_l_box, 3, 3)
        layout.addLayout(grid)
        layout.addWidget(self.buttonbox(save=True))
        self.setLayout(layout)
        self.setWindowTitle('Transforming Data')

        self.refine = NXRefine(self.root)
        self.refine.read_parameters()
        self.initialize_grid()

    def settings_box(self):
        """
        Creates a text box and button for selecting the settings file file.
        """
        file_button =  QtGui.QPushButton("Choose Settings File")
        file_button.clicked.connect(self.choose_settings_file)
        self.settings_file = QtGui.QLineEdit(self)
        self.settings_file.setMinimumWidth(300)
        file_box = QtGui.QHBoxLayout()
        file_box.addWidget(file_button)
        file_box.addWidget(self.settings_file)
        return file_box
 
    def output_box(self):
        """
        Creates a text box and button for selecting the output file.
        """
        file_button =  QtGui.QPushButton("Choose Output File")
        file_button.clicked.connect(self.choose_output_file)
        self.output_file = QtGui.QLineEdit(self)
        self.output_file.setMinimumWidth(300)
        file_box = QtGui.QHBoxLayout()
        file_box.addWidget(file_button)
        file_box.addWidget(self.output_file)
        return file_box
 
    def choose_settings_file(self):
        """
        Opens a file dialog and sets the settings file text box to the chosen path.
        """
        dirname = self.get_default_directory(self.get_settings_file())
        filename, _ = QtGui.QFileDialog.getOpenFileName(self, 'Choose Settings File',
                                                        dirname)
        if os.path.exists(dirname):    # avoids problems if <Cancel> was selected
            self.settings_file.setText(filename)
            self.set_default_directory(dirname)

    def choose_output_file(self):
        """
        Opens a file dialog and sets the settings file text box to the chosen path.
        """
        dirname = self.get_default_directory(self.get_output_file())
        filename, _ = QtGui.QFileDialog.getOpenFileName(self, 'Choose Output File',
                                                        dirname,
                                                        self.nexus_filter)
        if os.path.exists(dirname):    # avoids problems if <Cancel> was selected
            self.output_file.setText(filename)
            self.set_default_directory(dirname)

    def get_settings_file(self):
        return self.settings_file.text()

    def get_output_file(self):
        return self.output_file.text()

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

    def write_parameters(self):
        self.refine.settings_file = self.get_settings_file()
        self.refine.output_file = self.get_output_file()
        self.refine.data_shape = self.root[self.refine.data_path].shape
        self.refine.h_start, self.refine.h_step, self.refine.h_stop = self.get_h_grid()
        self.refine.k_start, self.refine.k_step, self.refine.k_stop = self.get_k_grid()
        self.refine.l_start, self.refine.l_step, self.refine.l_stop = self.get_l_grid()
        self.refine.define_grid()
        self.refine.data_file = self.root.nxfilename

    def accept(self):
        try:
            self.write_parameters()
            self.refine.initialize_output(self.get_output_file())
            self.refine.write_settings(self.get_settings_file())
            super(TransformDialog, self).accept()
        except NeXusError as error:
            report_error('Transforming Data', error)
