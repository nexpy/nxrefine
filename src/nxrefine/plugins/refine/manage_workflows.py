import os

from nexusformat.nexus import *
from nexpy.gui.pyqt import QtCore, QtWidgets
from nexpy.gui.datadialogs import BaseDialog
from nexpy.gui.utils import report_error, natural_sort

from nxrefine.nxreduce import Lock


def show_dialog():
    dialog = WorkflowDialog()
    dialog.show()
#    except NeXusError as error:
#        report_error("Defining New Experiment", error)


class WorkflowDialog(BaseDialog):

    def __init__(self, parent=None):
        super(WorkflowDialog, self).__init__(parent)

        self.set_layout(self.directorybox('Choose Sample Directory',
                                          slot=self.choose_directory),
                        self.close_buttons())
        self.set_title('Manage Workflows')
        self.sample_directory = None

    def choose_directory(self):
        super(WorkflowDialog, self).choose_directory()
        self.sample_directory = self.get_directory()
        self.sample = os.path.basename(os.path.dirname(self.sample_directory))
        self.mainwindow.default_directory = self.sample_directory
        self.insert_layout(1, self.prepare_grid())

    def prepare_grid(self):
        grid = QtWidgets.QGridLayout()
        grid.setSpacing(1)
        row = 0
        columns = ['Scan', 'nxlink', 'nxmax', 'nxfind', 'nxcopy', 'nxrefine', 
                   'nxtransform', 'nxcombine', 'overwrite']
        header = {}
        for col, column in enumerate(columns):
            header[column] = QtWidgets.QLabel(column)
            header[column].setFont(self.bold_font)
            header[column].setAlignment(QtCore.Qt.AlignHCenter)
            grid.addWidget(header[column], row, col)
        wrapper_files = sorted([os.path.join(self.sample_directory, filename) 
                            for filename in os.listdir(self.sample_directory) 
                            if filename.endswith('.nxs')], key=natural_sort)
        self.scan = {}
        for wrapper_file in wrapper_files:
            row += 1
            base_name = os.path.basename(os.path.splitext(wrapper_file)[0])
            directory = base_name.replace(self.sample+'_', '')
            status = {}
            with Lock(wrapper_file):
                root = nxload(wrapper_file)
            grid.addWidget(QtWidgets.QLabel(directory), row, 0, QtCore.Qt.AlignHCenter)
            status['nxlink'] = self.new_checkbox()
            status['nxmax'] = self.new_checkbox()
            status['nxfind'] = self.new_checkbox()
            status['nxcopy'] = self.new_checkbox()
            status['nxrefine'] = self.new_checkbox()
            status['nxtransform'] = self.new_checkbox()
            status['nxcombine'] = self.new_checkbox()
            status['overwrite'] = self.new_checkbox()
            for i,e in enumerate([entry for entry in root.entries if entry != 'entry']):
                if e in root and 'data' in root[e] and 'instrument' in root[e]:
                    self.update_checkbox(status['nxlink'], i,
                        'nxlink' in root[e] or 'logs' in root[e]['instrument'])
                    self.update_checkbox(status['nxmax'], i,
                        'nxmax' in root[e] or 'maximum' in root[e]['data'].attrs)
                    self.update_checkbox(status['nxfind'], i,
                        'nxfind' in root[e] or 'peaks' in root[e])
                    self.update_checkbox(status['nxcopy'], i, 'nxcopy' in root[e])
                    self.update_checkbox(status['nxrefine'], i,
                        'nxrefine' in root[e] or 
                        ('detector' in root[e]['instrument'] and 
                         'orientation_matrix' in root[e]['instrument/detector']))
                    self.update_checkbox(status['nxtransform'], i,
                        'nxtransform' in root[e] or 'transform' in root[e])
                else:
                    status['nxlink'].setEnabled(False)
                    status['nxmax'].setEnabled(False)
                    status['nxfind'].setEnabled(False)
                    status['nxcopy'].setEnabled(False)
                    status['nxrefine'].setEnabled(False)
                    status['nxtransform'].setEnabled(False)
                    status['overwrite'].setEnabled(False)
            self.update_checkbox(status['nxcombine'], 0,
                'nxcombine' in root['entry'] or 
                'transform' in root['entry'] or
                'masked_transform' in root['entry'])
            grid.addWidget(status['nxlink'], row, 1, QtCore.Qt.AlignHCenter)                   
            grid.addWidget(status['nxmax'], row, 2, QtCore.Qt.AlignHCenter)                   
            grid.addWidget(status['nxfind'], row, 3, QtCore.Qt.AlignHCenter)                   
            grid.addWidget(status['nxcopy'], row, 4, QtCore.Qt.AlignHCenter)                   
            grid.addWidget(status['nxrefine'], row, 5, QtCore.Qt.AlignHCenter)                   
            grid.addWidget(status['nxtransform'], row, 6, QtCore.Qt.AlignHCenter)                   
            grid.addWidget(status['nxcombine'], row, 7, QtCore.Qt.AlignHCenter)                   
            grid.addWidget(status['overwrite'], row, 8, QtCore.Qt.AlignHCenter)                  
            self.scan[directory] = status
        row += 1
        grid.addWidget(QtWidgets.QLabel('All'), row, 0, QtCore.Qt.AlignHCenter)
        all_boxes = {}
        all_boxes['nxlink'] = self.new_checkbox(self.choose_all)
        all_boxes['nxmax'] = self.new_checkbox(self.choose_all)
        all_boxes['nxfind'] = self.new_checkbox(self.choose_all)
        all_boxes['nxcopy'] = self.new_checkbox(self.choose_all)
        all_boxes['nxrefine'] = self.new_checkbox(self.choose_all)
        all_boxes['nxtransform'] = self.new_checkbox(self.choose_all)
        all_boxes['nxcombine'] = self.new_checkbox(self.choose_all)
        all_boxes['overwrite'] = self.new_checkbox(self.choose_all)        
        grid.addWidget(all_boxes['nxlink'], row, 1, QtCore.Qt.AlignHCenter)                   
        grid.addWidget(all_boxes['nxmax'], row, 2, QtCore.Qt.AlignHCenter)                   
        grid.addWidget(all_boxes['nxfind'], row, 3, QtCore.Qt.AlignHCenter)                   
        grid.addWidget(all_boxes['nxcopy'], row, 4, QtCore.Qt.AlignHCenter)                   
        grid.addWidget(all_boxes['nxrefine'], row, 5, QtCore.Qt.AlignHCenter)                   
        grid.addWidget(all_boxes['nxtransform'], row, 6, QtCore.Qt.AlignHCenter)                   
        grid.addWidget(all_boxes['nxcombine'], row, 7, QtCore.Qt.AlignHCenter)                   
        grid.addWidget(all_boxes['overwrite'], row, 8, QtCore.Qt.AlignHCenter)
        self.select_all = all_boxes                
        return grid

    def new_checkbox(self, slot=None):
        checkbox = QtWidgets.QCheckBox()
        checkbox.setCheckState(QtCore.Qt.Unchecked)
        checkbox.setEnabled(True)
        if slot:
            checkbox.stateChanged.connect(slot)
        return checkbox

    def update_checkbox(self, checkbox, idx, status):
        if status and idx == 0:
            checkbox.setCheckState(QtCore.Qt.Checked)
            checkbox.setEnabled(False)
        elif ((status and checkbox.checkState() == QtCore.Qt.Unchecked) or
              (not status and checkbox.checkState() == QtCore.Qt.Checked)):                    
            checkbox.setCheckState(QtCore.Qt.PartiallyChecked)
            checkbox.setEnabled(True)

    def choose_all(self, key):
        for status in self.select_all:
            for scan in self.scan:
                if self.scan[scan][status].isEnabled():
                    self.scan[scan][status].setCheckState(
                        self.select_all[status].checkState())                

    def accept(self):
        if not self.sample_directory:
            raise NeXusError('Sample directory not chosen')
        try:
            super(WorkflowDialog, self).accept()
        except Exception as error:
            report_error("Managing Workflows", error)
