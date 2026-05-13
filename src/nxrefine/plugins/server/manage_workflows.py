# -----------------------------------------------------------------------------
# Copyright (c) 2022, Argonne National Laboratory.
#
# Distributed under the terms of an Open Source License.
#
# The full license is in the file LICENSE.pdf, distributed with this software.
# -----------------------------------------------------------------------------

import subprocess
import time
from pathlib import Path

from nexpy.gui.pyqt import QtCore, QtWidgets
from nexpy.gui.utils import (format_mtime, human_size, natural_sort,
                             report_error)
from nexpy.gui.widgets import (NXDialog, NXLabel, NXPlainTextEdit,
                               NXPushButton, NXScrollArea, NXWidget)
from nexusformat.nexus import NeXusError, nxload

from nxrefine.nxdatabase import NXDatabase
from nxrefine.nxparent import NXParent
from nxrefine.nxreduce import NXMultiReduce, NXReduce
from nxrefine.nxserver import NXServer
from nxrefine.plugins.refine.select_files import FilesDialog


def show_dialog():
    try:
        dialog = WorkflowDialog()
        dialog.show()
    except NeXusError as error:
        report_error("Managing Workflows", error)


class WorkflowDialog(NXDialog):

    def __init__(self, parent=None):
        super().__init__(parent)

        self.set_layout(self.filebox('Choose Parent File'),
                        self.close_layout(close=True, progress=True))
        self.progress_bar.setVisible(False)
        self.set_title('Manage Workflows')
        self.grid = None
        self.scroll_area = None
        self.header_widget = None
        self.sample_directory = None
        self.entries = ['f1', 'f2', 'f3']
        self.server = None

    def __repr__(self):
        return f"WorkflowDialog('{self.sample_directory}')"

    def choose_file(self):
        super().choose_file(filter="Parent Files (*_scans.nxs)")
        self.parent_file = self.get_filename()
        if self.parent_file is None:
            return
        self.parent = NXParent(self.parent_file)
        if self.layout.count() == 2:
            self.insert_layout(1, self.subentry_layout())
            self.insert_layout(2, self.action_buttons(
                ('Select Scans', self.select_files),
                ('Update Status', self.update),
                ('Add to Queue', self.add_tasks),
                ('View Logs', self.view_logs),
                ('Sync Database', self.sync_db)))
        self.sample_directory = self.parent.filename.parent
        self.sample = self.sample_directory.parent.name
        self.label = self.sample_directory.name
        self.experiment_directory = self.sample_directory.parent.parent
        self.task_directory = self.experiment_directory / 'tasks'
        if not self.task_directory.exists():
            self.task_directory.mkdir()
        db_file = self.task_directory / 'nxdatabase.db'
        self.db = NXDatabase(db_file)
        if self.server is None:
            self.server = NXServer()
        self.refresh_subentries()
        self.update()
        self.set_default_directory(self.sample_directory)

    def select_files(self):
        dialog = FilesDialog(self.parent.filename, self.parent.subentry)
        dialog.accepted.connect(self.update)
        dialog.show()

    @property
    def subentry(self):
        return self.subentry_combo.selected

    def subentry_layout(self):
        self.subentry_combo = self.select_box(self.parent.scan_entries,
                                              default=self.parent.entry,
                                              slot=self.select_subentry)
        sub_button = NXPushButton('Create New Subentry', self.create_subentry)
        return self.make_layout(NXLabel('Subentry:'), self.subentry_combo,
                                'stretch', sub_button)

    def refresh_subentries(self):
        self.subentry_combo.blockSignals(True)
        current = self.subentry_combo.selected
        self.subentry_combo.clear()
        self.subentry_combo.add(*self.parent.scan_entries)
        if current in self.parent.scan_entries:
            self.subentry_combo.select(current)
        self.subentry_combo.blockSignals(False)

    def select_subentry(self):
        self.parent.entry = self.subentry
        self.update()

    def create_subentry(self):
        name = self.input_text('New Subentry', 'Enter subentry name:')
        if name is None:
            return
        self.parent.create_scan_entry(name)
        self.refresh_subentries()
        self.subentry_combo.select(f'/entry/{name}')

    def add_grid_headers(self):
        if self.header_widget is not None:
            self.header_widget.close()
            self.header_widget.deleteLater()
            self.header_widget = None

        self.header_grid = QtWidgets.QGridLayout()
        self.header_widget = NXWidget()
        self.header_widget.set_layout(self.header_grid)

        all_columns = (['Scan'] + self.tasks +
                       ['overwrite', 'sync'])
        header = {}
        for col, column in enumerate(all_columns):
            header[column] = NXLabel(
                column, bold=True, width=75, align='center')
            if column in ('transform', 'combine', 'pdf'):
                self.header_grid.addWidget(header[column], 0, col, 1, 2,
                                           QtCore.Qt.AlignHCenter)
            elif 'masked' not in column:
                self.header_grid.addWidget(header[column], 0, col)
                header[column].setAlignment(QtCore.Qt.AlignHCenter)
        transform_col = all_columns.index('transform')
        for col, label in enumerate(3 * ['regular', 'masked']):
            sub_label = NXLabel(label, width=75, align='center')
            self.header_grid.addWidget(sub_label, 1, col + transform_col)
        self.header_grid.setSpacing(0)
        self.header_widget.setFixedHeight(60)
        self.insert_layout(3, self.header_widget)

    def get_scan(self, filename):
        _base = Path(filename).stem
        _scan = _base.replace(self.sample+'_', '')
        return self.sample_directory / _scan

    def get_scan_file(self, scan):
        return self.sample_directory / (self.sample+'_'+Path(scan).name+'.nxs')

    def is_valid(self, wrapper_file):
        if not wrapper_file.endswith('.nxs'):
            return False
        elif not wrapper_file.startswith(self.sample):
            return False
        elif '_scans' in wrapper_file or '_mask' in wrapper_file:
            return False
        else:
            return True

    def update(self):
        if not self.sample_directory:
            raise NeXusError("No sample directory declared")

        if self.grid:
            self.delete_grid(self.grid)
            del self.grid_widget
        if self.scroll_area:
            self.scroll_area.close()
            self.scroll_area.deleteLater()

        self.add_grid_headers()

        # Map from wrapper files to scan directories
        files = self.parent.selected_scans
        wrapper_files = {self.sample_directory / f: self.get_scan(f)
                         for f in sorted(files, key=natural_sort)}
        self.grid = QtWidgets.QGridLayout()
        self.grid_widget = NXWidget()
        self.grid_widget.set_layout(self.grid, 'stretch')
        self.scroll_area = NXScrollArea(self.grid_widget)
        self.scroll_area.setMinimumSize(1250, 300)
        self.insert_layout(4, self.scroll_area)
        self.grid.setSpacing(1)

        self.scans = {}
        self.scans_backup = {}

        all_cols = ['scan'] + self.tasks + ['overwrite', 'sync']

        row = 0
        for wrapper_file, scan in wrapper_files.items():
            status = {}
            status['scan'] = NXLabel(scan.name)
            if self.parent_file == wrapper_file:
                status['scan'].setStyleSheet('font-weight:bold')
            status['entries'] = []
            for task in self.tasks:
                status[task] = self.new_checkbox()
            status['overwrite'] = self.new_checkbox(self.select_scans)
            status['sync'] = self.new_checkbox()
            for col, col_name in enumerate(all_cols):
                self.grid.addWidget(
                    status[col_name], row, col, QtCore.Qt.AlignCenter)
            self.scans[scan] = status
            row += 1

        self.grid.addWidget(NXLabel('All'), row, 0, QtCore.Qt.AlignCenter)
        all_boxes = {}
        for task in self.tasks:
            all_boxes[task] = self.new_checkbox(
                lambda t=task: self.select_status(t))
        all_boxes['overwrite'] = self.new_checkbox(self.select_all)
        all_boxes['sync'] = self.new_checkbox(self.select_all)
        for col, col_name in enumerate(all_cols):
            if col_name != 'scan':
                self.grid.addWidget(
                    all_boxes[col_name], row, col, QtCore.Qt.AlignCenter)
        self.all_scans = all_boxes
        self.start_progress((0, len(wrapper_files)))

        # Populate checkboxes from database
        for i, (wrapper, scan) in enumerate(wrapper_files.items()):
            status = self.scans[scan]
            f = self.db.get_file(wrapper)
            status['entries'] = f.get_entries()
            if self.parent.subentry:
                subentry_status = self.db.get_subentry_status(
                    wrapper, self.parent.subentry)
                for task_name in self.db.subentry_task_names:
                    col_name = task_name[2:]
                    self._set_checkbox(status[col_name],
                                       subentry_status.get(task_name,
                                                           self.db.NOT_STARTED))
            else:
                for task_name in self.db.task_names:
                    col_name = task_name[2:]
                    self._set_checkbox(status[col_name],
                                       getattr(f, task_name))
                if status['load'].checkState() == QtCore.Qt.Unchecked:
                    for task in ['link', 'max', 'find', 'prepare',
                                 'transform', 'masked_transform']:
                        status[task].setEnabled(False)
            self.update_progress(i)

        self.stop_progress()
        self.backup_scans()
        return self.grid

    def _set_checkbox(self, checkbox, file_status):
        if file_status == self.db.DONE:
            checkbox.setCheckState(QtCore.Qt.Checked)
            checkbox.setEnabled(False)
        elif file_status == self.db.IN_PROGRESS:
            checkbox.setCheckState(QtCore.Qt.PartiallyChecked)
            checkbox.setEnabled(True)
            checkbox.setStyleSheet("color: green")
        elif file_status == self.db.QUEUED:
            checkbox.setCheckState(QtCore.Qt.PartiallyChecked)
            checkbox.setEnabled(True)
            checkbox.setStyleSheet("color: blue")
        elif file_status == self.db.FAILED:
            checkbox.setCheckState(QtCore.Qt.PartiallyChecked)
            checkbox.setEnabled(True)
            checkbox.setStyleSheet("color: red")

    def sync_db(self):
        for scan in self.scans:
            if self.sync_selected(scan):
                self.db.update_file(self.get_scan_file(scan))
        self.update()

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

    def backup_scans(self):
        for scan in self.scans:
            self.scans_backup[scan] = []
            for status in self.tasks:
                self.scans_backup[scan].append(
                    (status,
                     self.scans[scan][status].isEnabled(),
                     self.scans[scan][status].checkState()))

    @property
    def tasks(self):
        if self.parent.subentry:
            return ['copy', 'max', 'find', 'refine', 'prepare',
                    'transform', 'masked_transform', 'combine',
                    'masked_combine', 'pdf', 'masked_pdf']
        return ['load', 'link', 'copy', 'max', 'find', 'refine', 'prepare',
                'transform', 'masked_transform', 'combine', 'masked_combine',
                'pdf', 'masked_pdf']

    @property
    def combined_tasks(self):
        return ['combine', 'masked_combine', 'pdf', 'masked_pdf']

    @property
    def enabled_scans(self):
        return self.scans

    def overwrite_selected(self, scan):
        return self.scans[scan]['overwrite'].isChecked()

    def sync_selected(self, scan):
        return self.scans[scan]['sync'].isChecked()

    def restore_scan(self, scan):
        for backup in self.scans_backup[scan]:
            status, enabled, checked = backup
            self.scans[scan][status].setEnabled(enabled)
            self.scans[scan][status].setCheckState(checked)

    def select_tasks(self, scan):
        if self.overwrite_selected(scan):
            for status in self.tasks:
                self.scans[scan][status].setEnabled(True)
        else:
            self.restore_scan(scan)
        if self.overwrite_selected(scan):
            for status in self.tasks:
                if self.scans[scan][status].isEnabled():
                    self.scans[scan][status].setChecked(
                        self.all_scans[status].isChecked())
        else:
            self.restore_scan(scan)

    def select_scans(self):
        for scan in self.enabled_scans:
            self.select_tasks(scan)

    def select_all(self):
        for scan in self.enabled_scans:
            self.scans[scan]['overwrite'].blockSignals(True)
            self.scans[scan]['overwrite'].setCheckState(
                self.all_scans['overwrite'].checkState())
            self.scans[scan]['overwrite'].blockSignals(False)
        for scan in self.scans:
            self.scans[scan]['sync'].setCheckState(
                self.all_scans['sync'].checkState())
        for scan in self.enabled_scans:
            self.select_tasks(scan)

    def select_status(self, status):
        for scan in self.enabled_scans:
            if self.scans[scan][status].isEnabled():
                self.scans[scan][status].setCheckState(
                    self.all_scans[status].checkState())

    def deselect_all(self):
        for scan in self.enabled_scans:
            self.scans[scan]['overwrite'].blockSignals(True)
            self.scans[scan]['overwrite'].setCheckState(False)
            self.scans[scan]['overwrite'].blockSignals(False)
        for scan in self.scans:
            self.scans[scan]['sync'].setCheckState(False)
        self.all_scans['overwrite'].blockSignals(True)
        self.all_scans['overwrite'].setChecked(False)
        self.all_scans['overwrite'].blockSignals(False)
        self.backup_scans()

    def selected(self, scan, task):
        return (self.scans[scan][task].isEnabled() and
                self.scans[scan][task].checkState() == QtCore.Qt.Checked)

    def any_selected(self, scan):
        for task in self.tasks:
            if self.selected(scan, task):
                return True
        return False

    def only_combined(self, scan):
        for task in [t for t in self.tasks if t not in self.combined_tasks]:
            if self.selected(scan, task):
                return False
        return True

    def queued(self, scan, task):
        self.scans[scan][task].setCheckState(QtCore.Qt.PartiallyChecked)
        self.scans[scan][task].setStyleSheet("")
        self.scans[scan][task].setEnabled(False)

    def add_tasks(self):
        if self.grid is None:
            raise NeXusError('Need to update status')
        for scan in [s for s in self.enabled_scans if self.any_selected(s)]:
            for i, entry in enumerate(self.enabled_scans[scan]['entries']):
                if self.only_combined(scan):
                    if i == 0:
                        reduce = NXMultiReduce(scan)
                        reduce.regular = reduce.mask = False
                    else:
                        break
                else:
                    reduce = NXReduce(entry, scan, server=self.server)
                    reduce.regular = reduce.mask = False
                    if not self.parent.subentry and self.selected(scan, 'load'):
                        reduce.load = True
                    if not self.parent.subentry and self.selected(scan, 'link'):
                        reduce.link = True
                    if self.selected(scan, 'copy'):
                        reduce.copy = True
                    if self.selected(scan, 'max'):
                        reduce.maxcount = True
                    if self.selected(scan, 'find'):
                        reduce.find = True
                    if self.selected(scan, 'refine'):
                        reduce.refine = True
                    if self.selected(scan, 'prepare'):
                        reduce.prepare = True
                    if self.selected(scan, 'transform'):
                        reduce.transform = True
                        reduce.regular = True
                    if self.selected(scan, 'masked_transform'):
                        reduce.transform = True
                        reduce.mask = True
                if self.selected(scan, 'combine'):
                    reduce.combine = True
                    reduce.regular = True
                if self.selected(scan, 'masked_combine'):
                    reduce.combine = True
                    reduce.mask = True
                if self.selected(scan, 'pdf'):
                    reduce.pdf = True
                    reduce.regular = True
                if self.selected(scan, 'masked_pdf'):
                    reduce.pdf = True
                    reduce.mask = True
                if self.selected(scan, 'overwrite'):
                    reduce.overwrite = True
                reduce.queue('nxreduce')
                time.sleep(0.5)
            for task in self.tasks:
                if self.selected(scan, task):
                    self.queued(scan, task)
        self.deselect_all()

    def view_logs(self):
        if self.grid is None:
            raise NeXusError('Need to update status')
        dialog = NXDialog(parent=self)
        dialog.setMinimumWidth(800)
        dialog.setMinimumHeight(600)
        scans = [scan.name for scan in self.scans]
        self.scan_combo = dialog.select_box(scans, slot=self.choose_scan)
        self.entry_combo = dialog.select_box(self.entries,
                                             slot=self.refreshview)
        self.task_combo = dialog.select_box(self.tasks, slot=self.refreshview)
        self.defaultview = None
        self.output_box = NXPlainTextEdit(wrap=False)
        cpu_process_button = NXPushButton('View CPU Processes', self.procview)
        cpu_log_button = NXPushButton('View CPU Log', self.cpuview)
        self.cpu_combo = dialog.select_box(['nxserver'] + self.server.cpus,
                                           slot=self.cpuview)
        close_layout = self.make_layout(cpu_process_button, cpu_log_button,
                                        self.cpu_combo, 'stretch',
                                        dialog.close_buttons(close=True),
                                        align='justified')
        dialog.set_layout(
            dialog.make_layout(self.scan_combo, self.entry_combo,
                               self.task_combo),
            self.output_box,
            dialog.action_buttons(('View Data Directory', self.dataview),
                                  ('View Server Logs', self.serverview),
                                  ('View Workflow Logs', self.logview),
                                  ('View Workflow Output', self.outview),
                                  ('View Database', self.databaseview)),
            close_layout)        
        dialog.setWindowTitle(
            f"{'/'.join(self.sample_directory.parts[-3:])} Logs")
        self.view_dialog = dialog
        self.view_dialog.show()

    def choose_scan(self):
        scan = self.sample_directory / self.scan_combo.selected
        current_entry = self.entry_combo.selected
        self.entry_combo.clear()
        self.entry_combo.add(*self.scans[scan]['entries'])
        if current_entry in self.entry_combo:
            self.entry_combo.select(current_entry)
        else:
            self.entry_combo.select(self.scans[scan]['entries'][0])
        self.refreshview()

    def dataview(self):
        self.defaultview = self.dataview
        scan = self.scan_combo.currentText()
        scan_directory = self.sample_directory / scan
        if not scan_directory.exists():
            self.output_box.setPlainText('Directory has not been created')
            return
        text = []

        def _getmtime(entry):
            return entry.stat().st_mtime
        for f in sorted(scan_directory.iterdir(), key=_getmtime):
            text.append('{0}   {1}   {2}'.format(
                format_mtime(f.stat().st_mtime),
                human_size(f.stat().st_size, width=6),
                f.name))
        if text:
            self.output_box.setPlainText('\n'.join(text))
        else:
            self.output_box.setPlainText('No Files')

    def serverview(self):
        self.defaultview = self.serverview
        scan = str(Path(self.sample) / self.label /
                   self.scan_combo.currentText())
        with open(self.server.server_log) as f:
            lines = f.readlines()
        text = [line for line in lines if scan in line]
        if text:
            self.output_box.setPlainText(''.join(text))
            self.output_box.verticalScrollBar().setValue(
                self.output_box.verticalScrollBar().maximum())
        else:
            self.output_box.setPlainText('No Logs')

    def logview(self):
        self.defaultview = self.logview
        scan = str(Path(self.label) /
                   (self.sample + '_' + self.scan_combo.currentText()))
        entry = self.entry_combo.currentText()
        prefix = scan + "['" + entry + "']: "
        alternate_prefix = scan + "['entry']: "
        with open(self.task_directory / 'nxlogger.log') as f:
            lines = f.readlines()
        text = [line.replace(prefix, '').replace(alternate_prefix, '')
                for line in lines if scan in line
                if (entry in line or 'entry' in line)]
        if text:
            self.output_box.setPlainText(''.join(text))
            self.output_box.verticalScrollBar().setValue(
                self.output_box.verticalScrollBar().maximum())
        else:
            self.output_box.setPlainText('No Logs')

    def outview(self):
        self.defaultview = self.outview
        scan = self.sample + '_' + self.scan_combo.currentText()
        entry = self.entry_combo.currentText()
        task = 'nx' + self.task_combo.currentText()
        if (task == 'nxcombine' or task == 'nxmasked_combine' or
                task == 'nxpdf'):
            entry = 'entry'
        wrapper_file = self.sample_directory / (scan+'.nxs')
        root = nxload(wrapper_file)
        if task in root[entry]:
            text = 'Date: ' + root[entry][task]['date'].nxvalue + '\n'
            text = text + root[entry][task]['note/data'].nxvalue
            self.output_box.setPlainText(text)
        else:
            self.output_box.setPlainText(f'No output for {task}')

    def databaseview(self):
        self.defaultview = self.databaseview
        scan = self.sample + '_' + self.scan_combo.currentText()
        task = 'nx' + self.task_combo.currentText()
        wrapper_file = self.sample_directory / (scan+'.nxs')
        f = self.db.get_file(wrapper_file)
        text = [' '.join([t.name, str(t.entry), str(t.status),
                          str(t.queue_time), str(t.start_time),
                          str(t.end_time)])
                for t in f.tasks if t.name == task]
        if text:
            self.output_box.setPlainText('\n'.join(text))
        else:
            self.output_box.setPlainText('No Entries')

    def procview(self):
        patterns = ['nxcombine', 'nxcopy', 'nxfind', 'nxlink', 'nxload',
                    'nxmax', 'nxpdf', 'nxprepare', 'nxreduce', 'nxrefine',
                    'nxsum', 'nxtransform']
        if self.server.run_command.startswith('pdsh'):
            command = "pdsh -w {} 'ps -f' | grep -e {}".format(
                ",".join(self.server.cpus), " -e ".join(patterns))
        else:
            command = f"ps auxww | grep -e {' -e '.join(patterns)}"
        process = subprocess.run(command, shell=True, stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE)
        if process.returncode == 0:
            lines = [line for line in sorted(
                process.stdout.decode().split('\n')) if line]
            lines = [line[line.index('nx'):]
                     for line in lines if 'grep' not in line]
            self.output_box.setPlainText('\n'.join(set(lines)))
        else:
            self.output_box.setPlainText(process.stderr.decode())

    def cpuview(self):
        cpu = self.cpu_combo.selected
        cpu_log = self.server.directory / f'{cpu}.log'
        if cpu_log.exists():
            with open(cpu_log) as f:
                lines = f.readlines()
            self.output_box.setPlainText(''.join(lines))
            self.output_box.verticalScrollBar().setValue(
                self.output_box.verticalScrollBar().maximum())
        else:
            self.output_box.setPlainText('No Logs')

    def refreshview(self):
        if self.defaultview:
            self.defaultview()

    def closeEvent(self, event):
        if self.server is not None and self.server.server_type == 'direct':
            self.server.stop()
        super().closeEvent(event)

    def reject(self):
        if self.server is not None and self.server.server_type == 'direct':
            self.server.stop()
        super().reject()        
