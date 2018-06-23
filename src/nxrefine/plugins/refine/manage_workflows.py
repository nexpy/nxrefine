import os

from nexusformat.nexus import *
from nexpy.gui.pyqt import QtCore, QtWidgets
from nexpy.gui.datadialogs import BaseDialog, GridParameters
from nexpy.gui.utils import report_error, natural_sort

from nxrefine.nxreduce import Lock, NXReduce, NXMultiReduce


def show_dialog():
    try:
        dialog = WorkflowDialog()
        dialog.show()
    except NeXusError as error:
        report_error("Managing Workflows", error)


class WorkflowDialog(BaseDialog):

    def __init__(self, parent=None):
        super(WorkflowDialog, self).__init__(parent)

        self.set_layout(self.directorybox('Choose Sample Directory', default=False),
                        self.filebox('Choose Parent File'),
                        self.action_buttons(('Update Status', self.update),
                                            ('Add to Queue', self.add_tasks),
                                            ('View Logs', self.view_logs)),
                        self.progress_layout(close=True))
        self.progress_bar.setVisible(False)
        self.set_title('Manage Workflows')
        self.grid = None
        self.sample_directory = None
        self.entries = []
        self.layout.setSizeConstraint(QtWidgets.QLayout.SetFixedSize)

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
        self.task_directory = os.path.join(self.root_directory, 'tasks')
        self.mainwindow.default_directory = self.sample_directory
        if self.grid:
            self.delete_grid(self.grid)
            self.grid = None

    def choose_file(self):
        super(WorkflowDialog, self).choose_file()
        self.make_parent()

    def get_scan(self, filename):
        _base = os.path.basename(os.path.splitext(filename)[0])
        _scan = _base.replace(self.sample+'_', '')
        return os.path.join(self.sample_directory, _scan)    

    def make_parent(self):
        reduce = NXReduce(directory=self.get_scan(self.get_filename()), 
                          overwrite=True)
        reduce.make_parent()
        if self.grid:
            self.delete_grid(self.grid)
            self.grid = None
            self.update()

    def is_valid(self, wrapper_file):
        if not wrapper_file.endswith('.nxs'):
            return False
        elif not os.path.basename(wrapper_file).startswith(self.sample):
            return False
        elif '_parent' in wrapper_file or '_mask' in wrapper_file:
            return False
        else:
            return True

    def update(self):
        wrapper_files = sorted([os.path.join(self.sample_directory, filename) 
                            for filename in os.listdir(self.sample_directory) 
                            if self.is_valid(filename)], key=natural_sort)
        if self.grid and self.grid.rowCount() == len(wrapper_files) + 2:
            row = 0
        else:
            if self.grid:
                self.delete_grid(self.grid)
            self.grid = QtWidgets.QGridLayout()
            self.insert_layout(2, self.grid)
            self.grid.setSpacing(1)
            row = 0
            columns = ['Scan', 'data', 'link', 'max', 'find', 'copy', 'refine', 
                   'transform', 'combine', 'overwrite', 'reduce']
            header = {}
            for col, column in enumerate(columns):
                header[column] = QtWidgets.QLabel(column)
                header[column].setFont(self.bold_font)
                header[column].setFixedWidth(75)
                header[column].setAlignment(QtCore.Qt.AlignHCenter)
                self.grid.addWidget(header[column], row, col)
        self.scans = {}
        self.scans_backup = {}
        for wrapper_file in wrapper_files:
            scan = self.get_scan(wrapper_file)
            scan_label = os.path.basename(scan)
            row += 1
            if row == 1:
                with Lock(wrapper_file):
                    root = nxload(wrapper_file)
                    self.entries = [e for e in root.entries if e != 'entry']
            status = {}
            status['scan'] = QtWidgets.QLabel(scan_label)
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
            self.grid.addWidget(status['scan'], row, 0, QtCore.Qt.AlignCenter)
            self.grid.addWidget(status['data'], row, 1, QtCore.Qt.AlignCenter)                   
            self.grid.addWidget(status['link'], row, 2, QtCore.Qt.AlignCenter)                   
            self.grid.addWidget(status['max'], row, 3, QtCore.Qt.AlignCenter)                   
            self.grid.addWidget(status['find'], row, 4, QtCore.Qt.AlignCenter)
            self.grid.addWidget(status['copy'], row, 5, QtCore.Qt.AlignCenter)
            self.grid.addWidget(status['refine'], row, 6, QtCore.Qt.AlignCenter)
            self.grid.addWidget(status['transform'], row, 7, QtCore.Qt.AlignCenter)                   
            self.grid.addWidget(status['combine'], row, 8, QtCore.Qt.AlignCenter)                   
            self.grid.addWidget(status['overwrite'], row, 9, QtCore.Qt.AlignCenter)                  
            self.grid.addWidget(status['reduce'], row, 10, QtCore.Qt.AlignCenter)
            self.scans[scan] = status
        row += 1
        self.grid.addWidget(QtWidgets.QLabel('All'), row, 0, QtCore.Qt.AlignCenter)
        all_boxes = {}
        all_boxes['combine'] = self.new_checkbox(self.combine_all)
        all_boxes['overwrite'] = self.new_checkbox(self.select_all)
        all_boxes['reduce'] = self.new_checkbox(self.select_all)        
        self.grid.addWidget(all_boxes['combine'], row, 8, QtCore.Qt.AlignCenter)
        self.grid.addWidget(all_boxes['overwrite'], row, 9, QtCore.Qt.AlignCenter)
        self.grid.addWidget(all_boxes['reduce'], row, 10, QtCore.Qt.AlignCenter)
        self.all_scans = all_boxes
        self.start_progress((0, len(wrapper_files)))
        for (i, scan) in enumerate(self.scans):
            status = self.scans[scan]
            for (j, entry) in enumerate(self.entries):
                r = NXReduce(entry, scan)
                self.update_checkbox(status['data'], j, r.data_exists())
                self.update_checkbox(status['link'], j, r.complete('nxlink'))
                self.update_checkbox(status['max'], j, r.complete('nxmax'))
                self.update_checkbox(status['find'], j, r.complete('nxfind'))
                if r.is_parent():
                    self.update_checkbox(status['copy'], j, True)
                    status['scan'].setStyleSheet("font-weight: bold;")
                else:
                    self.update_checkbox(status['copy'], j, r.complete('nxcopy'))
                    status['scan'].setStyleSheet("font-weight: normal;")
                self.update_checkbox(status['refine'], j, r.complete('nxrefine'))
                self.update_checkbox(status['transform'], j, r.complete('nxtransform'))
                self.update_checkbox(status['combine'], j, r.complete('nxcombine'))
                status['data'].setEnabled(False)
            if self.scans[scan]['data'].checkState() == QtCore.Qt.Unchecked:
                self.disable_status(self.scans[scan])
            self.update_checkbox(status['combine'], 0, r.complete('nxcombine'))
            self.update_progress(i)
        self.stop_progress()       
        self.backup_scans()           
        return self.grid

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
        for program in self.programs:
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

    def deselect_all(self):
        for scan in self.enabled_scans:
            for status in ['overwrite', 'reduce']:
                self.scans[scan][status].blockSignals(True)
            for status in ['overwrite', 'reduce']:
                self.scans[scan][status].setCheckState(False)
            for status in ['overwrite', 'reduce']:
                self.scans[scan][status].blockSignals(False)
        for status in ['overwrite', 'reduce']:
            self.all_scans[status].blockSignals(True)
            self.all_scans[status].setChecked(False)
            self.all_scans[status].blockSignals(False)
        self.backup_scans()

    def combine_all(self):
        for scan in self.enabled_scans:
            if self.scans[scan]['combine'].isEnabled():
                self.scans[scan]['combine'].setCheckState(
                    self.all_scans['combine'].checkState())

    def selected(self, scan, command):
        return (self.scans[scan][command].isEnabled() and 
                self.scans[scan][command].checkState()==QtCore.Qt.Checked)

    def queued(self, scan, program):
        self.scans[scan][program].setChecked(False)
        self.scans[scan][program].setEnabled(False)
    
    def add_tasks(self):
        if self.grid is None:
            raise NeXusError('Need to update status')
        for scan in self.enabled_scans:
            for entry in self.entries:
                reduce = NXReduce(entry, scan)
                if self.selected(scan, 'link'):
                    reduce.link = True
                    self.queued(scan, 'link')
                if self.selected(scan, 'max'):
                    reduce.maxcount = True
                    self.queued(scan, 'max')
                if self.selected(scan, 'find'):
                    reduce.find = True
                    self.queued(scan, 'find')
                if self.selected(scan, 'copy'):
                    reduce.copy = True
                    self.queued(scan, 'copy')
                if self.selected(scan, 'refine'):
                    reduce.refine = True
                    self.queued(scan, 'refine')
                if self.selected(scan, 'transform'):
                    reduce.transform = True
                    self.queued(scan, 'transform')
                if self.selected(scan, 'overwrite'):
                    reduce.overwrite = True
                reduce.queue()
            if self.selected(scan, 'combine'):
                reduce = NXMultiReduce(scan, self.entries)
                if self.selected(scan, 'overwrite'):
                    reduce.overwrite = True
                reduce.queue()
                self.queued(scan, 'combine')
            self.scans[scan]
        self.deselect_all()
        

    def view_logs(self):
        if self.grid is None:
            raise NeXusError('Need to update status')
        dialog = BaseDialog(self)
        dialog.setMinimumWidth(800)
        dialog.setMinimumHeight(600)
        scans = [os.path.basename(scan) for scan in self.scans]
        self.scan_combo = dialog.select_box(scans)
        self.entry_combo = dialog.select_box(self.entries)
        self.program_combo = dialog.select_box(self.programs)
        self.output_box = dialog.editor()
        self.output_box.setStyleSheet('font-family: monospace;')
        dialog.set_layout(
            dialog.make_layout(self.scan_combo, self.entry_combo, self.program_combo),
            self.output_box,
            dialog.action_buttons(('View Server Logs', self.serverview),
                                  ('View Workflow Logs', self.logview),
                                  ('View Workflow Output', self.outview)),
            dialog.close_buttons(close=True))
        dialog.setWindowTitle("'%s' Logs" % self.sample)
        self.view_dialog = dialog
        self.view_dialog.show()

    def serverview(self):
        scan = self.scan_combo.currentText()
        with open(os.path.join(self.task_directory, 'nxserver.log')) as f:
            lines = f.readlines()
        text = [line for line in lines 
                if self.sample in line if scan in line]
        if text:
            self.output_box.setPlainText(''.join(text))
        else:
            self.output_box.setPlainText('No Logs')

    def logview(self):
        scan = self.sample + '_' + self.scan_combo.currentText()
        entry = self.entry_combo.currentText()
        prefix = scan + "['" + entry + "']: "
        with open(os.path.join(self.task_directory, 'nxlogger.log')) as f:
            lines = f.readlines()
        text = [line.replace(prefix, '') for line in lines 
                if scan in line if entry in line]
        if text:
            self.output_box.setPlainText(''.join(text))
        else:
            self.output_box.setPlainText('No Logs')

    def outview(self):
        scan = self.sample + '_' + self.scan_combo.currentText()
        entry = self.entry_combo.currentText()
        program = 'nx' + self.program_combo.currentText()
        if program == 'nxcombine':
            entry = 'entry'
        wrapper_file = os.path.join(self.sample_directory, scan+'.nxs')
        with Lock(wrapper_file):
            root = nxload(wrapper_file)
        if program in root[entry]:
            text = 'Date: ' + root[entry][program]['date'].nxvalue + '\n'
            text = text + root[entry][program]['note/data'].nxvalue
            self.output_box.setPlainText(text)
        else:
            self.output_box.setPlainText('No output for %s' % program)
