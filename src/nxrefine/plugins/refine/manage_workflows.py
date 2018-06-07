import os

from nexusformat.nexus import *
from nexpy.gui.pyqt import QtCore, QtWidgets
from nexpy.gui.datadialogs import BaseDialog, GridParameters
from nexpy.gui.utils import report_error, natural_sort

from nxrefine.nxreduce import Lock, NXReduce


def show_dialog():
    dialog = WorkflowDialog()
    dialog.show()
#    except NeXusError as error:
#        report_error("Defining New Experiment", error)


class WorkflowDialog(BaseDialog):

    def __init__(self, parent=None):
        super(WorkflowDialog, self).__init__(parent)

        self.set_layout(self.directorybox('Choose Sample Directory'),
                        self.filebox('Choose Parent File'),
                        self.action_buttons(('Update Status', self.update),
                                            ('Add to Queue', self.add_tasks)),
                        self.close_buttons(close=True))
        self.set_title('Manage Workflows')
        self.grid = None
        self.sample_directory = None
        self.entries = []

    def choose_directory(self):
        super(WorkflowDialog, self).choose_directory()
        self.sample_directory = self.get_directory()
        self.sample = os.path.basename(os.path.dirname(self.sample_directory))
        parent_file = os.path.join(self.sample_directory, 
                                   self.sample+'_parent.nxs')
        if os.path.exists(parent_file):
            self.filename.setText(os.path.basename(os.path.realpath(parent_file)))
        else:
            self.filename.setText('')
        self.root_directory = os.path.dirname(os.path.dirname(self.sample_directory))
        self.mainwindow.default_directory = self.sample_directory
        if self.grid:
            self.delete_grid(self.grid)
            self.grid = None

    def choose_file(self):
        super(WorkflowDialog, self).choose_file()
        self.make_parent()

    def make_parent(self):
        _parent = self.get_filename()
        _base = os.path.basename(os.path.splitext(_parent)[0])
        _scan = _base.replace(self.sample+'_', '')
        reduce = NXReduce(directory=os.path.join(self.sample_directory, _scan), 
                          overwrite=True)
        reduce.make_parent()

    def is_parent(self, wrapper_file):
        parent_file = os.path.join(self.sample_directory, 
                                   self.sample+'_parent.nxs')
        if os.path.exists(parent_file):
            return wrapper_file == os.path.realpath(parent_file)
        else:
            return False

    def update(self):
        grid = QtWidgets.QGridLayout()
        grid.setSpacing(1)
        row = 0
        columns = ['Scan', 'nxlink', 'nxmax', 'nxfind', 'nxcopy', 'nxrefine', 
                   'nxtransform', 'nxcombine', 'overwrite', 'reduce']
        header = {}
        for col, column in enumerate(columns):
            header[column] = QtWidgets.QLabel(column)
            header[column].setFont(self.bold_font)
            header[column].setAlignment(QtCore.Qt.AlignHCenter)
            grid.addWidget(header[column], row, col)
        wrapper_files = sorted([os.path.join(self.sample_directory, filename) 
                            for filename in os.listdir(self.sample_directory) 
                            if filename.endswith('.nxs')], key=natural_sort)
        self.scans = {}
        for wrapper_file in wrapper_files:
            row += 1
            base_name = os.path.basename(os.path.splitext(wrapper_file)[0])
            scan_label = base_name.replace(self.sample+'_', '')
            if scan_label == 'parent':
                break
            directory = os.path.join(self.sample_directory, scan_label)
            status = {}
            with Lock(wrapper_file):
                root = nxload(wrapper_file)
                self.entries = [e for e in root.entries if e != 'entry']
            grid.addWidget(QtWidgets.QLabel(scan_label), row, 0, QtCore.Qt.AlignHCenter)
            status['link'] = self.new_checkbox()
            status['max'] = self.new_checkbox()
            status['find'] = self.new_checkbox()
            status['copy'] = self.new_checkbox()
            status['refine'] = self.new_checkbox()
            status['transform'] = self.new_checkbox()
            status['combine'] = self.new_checkbox()
            status['overwrite'] = self.new_checkbox() 
            status['reduce'] = self.new_checkbox() 
            for i,e in enumerate(self.entries):
                if e in root and 'data' in root[e] and 'instrument' in root[e]:
                    self.update_checkbox(status['link'], i,
                        'nxlink' in root[e] or 'logs' in root[e]['instrument'])
                    self.update_checkbox(status['max'], i,
                        'nxmax' in root[e] or 'maximum' in root[e]['data'].attrs)
                    self.update_checkbox(status['find'], i,
                        'nxfind' in root[e] or 'peaks' in root[e])
                    self.update_checkbox(status['copy'], i, 
                        'nxcopy' in root[e] or self.is_parent(wrapper_file))
                    self.update_checkbox(status['refine'], i, 
                        'nxrefine' in root[e])
                    self.update_checkbox(status['transform'], i,
                        'nxtransform' in root[e])
                else:
                    status['link'].setEnabled(False)
                    status['max'].setEnabled(False)
                    status['find'].setEnabled(False)
                    status['copy'].setEnabled(False)
                    status['refine'].setEnabled(False)
                    status['transform'].setEnabled(False)
                    status['reduce'].setEnabled(False)
                    status['overwrite'].setEnabled(False)
            self.update_checkbox(status['combine'], 0, 
                                 'combine' in root['entry'])
            grid.addWidget(status['link'], row, 1, QtCore.Qt.AlignHCenter)                   
            grid.addWidget(status['max'], row, 2, QtCore.Qt.AlignHCenter)                   
            grid.addWidget(status['find'], row, 3, QtCore.Qt.AlignHCenter)                   
            grid.addWidget(status['copy'], row, 4, QtCore.Qt.AlignHCenter)                   
            grid.addWidget(status['refine'], row, 5, QtCore.Qt.AlignHCenter)                   
            grid.addWidget(status['transform'], row, 6, QtCore.Qt.AlignHCenter)                   
            grid.addWidget(status['combine'], row, 7, QtCore.Qt.AlignHCenter)                   
            grid.addWidget(status['overwrite'], row, 8, QtCore.Qt.AlignHCenter)                  
            grid.addWidget(status['reduce'], row, 9, QtCore.Qt.AlignHCenter)                  
            self.scans[directory] = status
        row += 1
        grid.addWidget(QtWidgets.QLabel('All'), row, 0, QtCore.Qt.AlignHCenter)
        all_boxes = {}
        all_boxes['link'] = self.new_checkbox(self.choose_all_scans)
        all_boxes['max'] = self.new_checkbox(self.choose_all_scans)
        all_boxes['find'] = self.new_checkbox(self.choose_all_scans)
        all_boxes['copy'] = self.new_checkbox(self.choose_all_scans)
        all_boxes['refine'] = self.new_checkbox(self.choose_all_scans)
        all_boxes['transform'] = self.new_checkbox(self.choose_all_scans)
        all_boxes['combine'] = self.new_checkbox(self.choose_all_scans)
        all_boxes['overwrite'] = self.new_checkbox(self.choose_all_scans)        
        all_boxes['reduce'] = self.new_checkbox(self.choose_all_scans)        
        grid.addWidget(all_boxes['link'], row, 1, QtCore.Qt.AlignHCenter)                   
        grid.addWidget(all_boxes['max'], row, 2, QtCore.Qt.AlignHCenter)                   
        grid.addWidget(all_boxes['find'], row, 3, QtCore.Qt.AlignHCenter)                   
        grid.addWidget(all_boxes['copy'], row, 4, QtCore.Qt.AlignHCenter)                   
        grid.addWidget(all_boxes['refine'], row, 5, QtCore.Qt.AlignHCenter)                   
        grid.addWidget(all_boxes['transform'], row, 6, QtCore.Qt.AlignHCenter)                   
        grid.addWidget(all_boxes['combine'], row, 7, QtCore.Qt.AlignHCenter)                   
        grid.addWidget(all_boxes['overwrite'], row, 8, QtCore.Qt.AlignHCenter)
        grid.addWidget(all_boxes['reduce'], row, 9, QtCore.Qt.AlignHCenter)
        self.all_scans = all_boxes
        if self.grid:
            self.delete_grid(self.grid)
        self.grid = grid
        self.insert_layout(2, self.grid)           
        return grid

    def new_checkbox(self, slot=None):
        checkbox = QtWidgets.QCheckBox()
        checkbox.setCheckState(QtCore.Qt.Unchecked)
        checkbox.setEnabled(True)
        checkbox.setFixedWidth(200)
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

    def choose_all_scans(self):
        for status in self.all_scans:
            for scan in self.scans:
                if self.scans[scan][status].isEnabled():
                    self.scans[scan][status].setCheckState(
                        self.all_scans[status].checkState())                

    def selected(self, scan, command):
        return (self.scans[scan][command].isEnabled() and 
                self.scans[scan][command].isChecked())
    
    def add_tasks(self):
        for scan in self.scans:
            if self.scans[scan]['reduce'].isChecked():
                for entry in self.entries:
                    reduce = NXReduce(entry, scan)
                    if self.selected(scan, 'link'):
                        reduce.link = True
                    if self.selected(scan, 'max'):
                        reduce.maxcount = True
                    if self.selected(scan, 'find'):
                        reduce.find = True
                    if self.selected(scan, 'copy'):
                        reduce.copy = True
                    if self.selected(scan, 'refine'):
                        reduce.refine = True
                    if self.selected(scan, 'overwrite'):
                        reduce.overwrite=True
                    reduce.queue()                            
