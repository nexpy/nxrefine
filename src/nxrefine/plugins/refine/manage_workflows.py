import os

from nexusformat.nexus import *
from nexpy.gui.pyqt import QtCore, QtWidgets
from nexpy.gui.datadialogs import BaseDialog, GridParameters
from nexpy.gui.utils import report_error, natural_sort

from nxrefine.nxreduce import Lock, NXReduce, NXMultiReduce


def show_dialog():
    dialog = WorkflowDialog()
    dialog.show()
#    except NeXusError as error:
#        report_error("Defining New Experiment", error)


class WorkflowDialog(BaseDialog):

    def __init__(self, parent=None):
        super(WorkflowDialog, self).__init__(parent)

        self.set_layout(self.directorybox('Choose Sample Directory', default=False),
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
        columns = ['Scan', 'data', 'link', 'max', 'find', 'copy', 'refine', 
                   'transform', 'combine', 'overwrite', 'reduce']
        header = {}
        for col, column in enumerate(columns):
            header[column] = QtWidgets.QLabel(column)
            header[column].setFont(self.bold_font)
            header[column].setFixedWidth(75)
            header[column].setAlignment(QtCore.Qt.AlignHCenter)
            grid.addWidget(header[column], row, col)
        wrapper_files = sorted([os.path.join(self.sample_directory, filename) 
                            for filename in os.listdir(self.sample_directory) 
                            if filename.endswith('.nxs')], key=natural_sort)
        self.scans = {}
        self.scans_backup = {}
        for wrapper_file in wrapper_files:
            row += 1
            base_name = os.path.basename(os.path.splitext(wrapper_file)[0])
            scan_label = base_name.replace(self.sample+'_', '')
            if scan_label == 'parent' or scan_label == 'mask':
                break
            directory = os.path.join(self.sample_directory, scan_label)
            status = {}
            with Lock(wrapper_file):
                root = nxload(wrapper_file)
                self.entries = [e for e in root.entries if e != 'entry']
            grid.addWidget(QtWidgets.QLabel(scan_label), row, 0, QtCore.Qt.AlignHCenter)
            status['data'] = self.new_checkbox()
            status['link'] = self.new_checkbox()
            status['max'] = self.new_checkbox()
            status['find'] = self.new_checkbox()
            status['copy'] = self.new_checkbox()
            status['refine'] = self.new_checkbox()
            status['transform'] = self.new_checkbox()
            status['combine'] = self.new_checkbox()
            status['overwrite'] = self.new_checkbox(self.select_scans) 
            status['reduce'] = self.new_checkbox(self.select_scans) 
            for i,e in enumerate(self.entries):
                r = NXReduce(root[e])
                self.update_checkbox(status['data'], i, r.data_exists())
                self.update_checkbox(status['link'], i, r.complete('nxlink'))
                self.update_checkbox(status['max'], i, r.complete('nxmax'))
                self.update_checkbox(status['find'], i, r.complete('nxfind'))
                self.update_checkbox(status['copy'], i, 
                    r.complete('nxcopy') or self.is_parent(wrapper_file))
                self.update_checkbox(status['refine'], i, r.complete('nxrefine'))
                self.update_checkbox(status['transform'], i, r.complete('nxtransform'))
                self.update_checkbox(status['combine'], i, r.complete('nxcombine'))
                status['data'].setEnabled(False)
            self.update_checkbox(status['combine'], 0, r.complete('nxcombine'))
            grid.addWidget(status['data'], row, 1, QtCore.Qt.AlignCenter)                   
            grid.addWidget(status['link'], row, 2, QtCore.Qt.AlignCenter)                   
            grid.addWidget(status['max'], row, 3, QtCore.Qt.AlignCenter)                   
            grid.addWidget(status['find'], row, 4, QtCore.Qt.AlignCenter)
            grid.addWidget(status['copy'], row, 5, QtCore.Qt.AlignCenter)
            grid.addWidget(status['refine'], row, 6, QtCore.Qt.AlignCenter)
            grid.addWidget(status['transform'], row, 7, QtCore.Qt.AlignCenter)                   
            grid.addWidget(status['combine'], row, 8, QtCore.Qt.AlignCenter)                   
            grid.addWidget(status['overwrite'], row, 9, QtCore.Qt.AlignCenter)                  
            grid.addWidget(status['reduce'], row, 10, QtCore.Qt.AlignCenter)
            self.scans[directory] = status
            if self.scans[directory]['data'].checkState() == QtCore.Qt.Unchecked:
                self.disable_status(self.scans[directory])
        self.backup_scans()           
        row += 1
        grid.addWidget(QtWidgets.QLabel('All'), row, 0, QtCore.Qt.AlignCenter)
        all_boxes = {}
        all_boxes['combine'] = self.new_checkbox(self.combine_all)
        all_boxes['overwrite'] = self.new_checkbox(self.select_all)
        all_boxes['reduce'] = self.new_checkbox(self.select_all)        
        grid.addWidget(all_boxes['combine'], row, 8, QtCore.Qt.AlignCenter)
        grid.addWidget(all_boxes['overwrite'], row, 9, QtCore.Qt.AlignCenter)
        grid.addWidget(all_boxes['reduce'], row, 10, QtCore.Qt.AlignCenter)
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

    def disable_status(self, status):
        for program in status:
            status[program].setEnabled(False)

    def backup_scans(self):
        for scan in self.scans:
            self.scans_backup[scan] = []
            for status in self.programs:
                self.scans_backup[scan].append(
                    (status, 
                     self.scans[scan][status].isEnabled(),
                     self.scans[scan][status].checkState()))

    @property
    def programs(self):
        return ['link', 'max', 'find', 'copy', 'refine', 'transform', 'combine']

    @property
    def enabled_scans(self):
        return [scan for scan in self.scans 
                if self.scans[scan]['data'].isChecked()]

    def overwrite_selected(self, scan):
        return self.scans[scan]['overwrite'].isChecked()

    def reduce_selected(self, scan):
        return self.scans[scan]['reduce'].isChecked()

    def restore_scan(self, scan):
        for backup in self.scans_backup[scan]:
            status, enabled, checked = backup
            self.scans[scan][status].setEnabled(enabled)
            self.scans[scan][status].setCheckState(checked)
    
    def select_programs(self, scan):
        if self.overwrite_selected(scan):
            for status in self.programs:
                self.scans[scan][status].setEnabled(True)
        else:
            self.restore_scan(scan)
        if self.reduce_selected(scan):
            for status in self.programs:
                if self.scans[scan][status].isEnabled():
                    self.scans[scan][status].setChecked(True)
        else:
            if self.overwrite_selected(scan):
                for status in self.programs:
                    if self.scans[scan][status].isEnabled():
                        self.scans[scan][status].setChecked(False)
            else:    
                self.restore_scan(scan)

    def select_scans(self):
        for scan in self.enabled_scans:
            self.select_programs(scan)

    def select_all(self):
        for scan in self.enabled_scans:
            for status in ['overwrite', 'reduce']:
                self.scans[scan][status].blockSignals(True)
            for status in ['overwrite', 'reduce']:
                self.scans[scan][status].setCheckState(
                    self.all_scans[status].checkState())
            for status in ['overwrite', 'reduce']:
                self.scans[scan][status].blockSignals(False)
        for scan in self.enabled_scans:
            self.select_programs(scan)

    def combine_all(self):
        for scan in self.enabled_scans:
            if self.scans[scan]['combine'].isEnabled():
                self.scans[scan]['combine'].setCheckState(
                    self.all_scans['combine'].checkState())

    def selected(self, scan, command):
        return (self.scans[scan][command].isEnabled() and 
                self.scans[scan][command].checkState()==QtCore.Qt.Checked)
    
    def add_tasks(self):
        for scan in self.enabled_scans:
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
                if self.selected(scan, 'transform'):
                    reduce.transform = True
                if self.selected(scan, 'overwrite'):
                    reduce.overwrite = True
                reduce.queue()
            if self.selected(scan, 'combine'):
                reduce = NXMultiReduce(scan, self.entries)
                if self.selected(scan, 'overwrite'):
                    reduce.overwrite = True
                reduce.queue()
                
