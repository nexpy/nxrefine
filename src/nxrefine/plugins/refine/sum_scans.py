from __future__ import unicode_literals
import os
import numpy as np
import timeit
from shutil import copyfile
from nexusformat.nexus import *
from nexpy.gui.datadialogs import NXWidget, NXDialog
from nexpy.gui.utils import report_error, confirm_action, natural_sort
from nexpy.gui.widgets import NXScrollArea
from nexpy.gui.pyqt import QtCore, getSaveFileName
from nxrefine.nxserver import NXServer
from nxrefine.nxreduce import NXReduce


def show_dialog():
    try:
        dialog = SumDialog()
        dialog.show()
    except NeXusError as error:
        report_error("Summing Scans", error)


class SumDialog(NXDialog):

    def __init__(self, parent=None):
        super(SumDialog, self).__init__(parent)
        self.scans = None
        self.set_layout(self.directorybox("Choose Sample Directory",
                                          self.choose_sample),
                        self.action_buttons(('Select All', self.select_scans),
                                            ('Clear All', self.clear_scans),
                                            ('Sum Scans', self.sum_scans)),
                        self.checkboxes(('update', 'Update Existing File', False),
                                        ('overwrite', 'Overwrite Existing File', False)),
                        self.close_layout(close=True))
        self.set_title('Sum Files')

    def choose_sample(self):
        super(SumDialog, self).choose_directory()
        self.sample_directory = self.get_directory()
        self.experiment_directory = os.path.dirname(os.path.dirname(self.sample_directory))
        self.sample = os.path.basename(os.path.dirname(self.sample_directory))
        self.setup_scans()

    def setup_scans(self):
        scans = []
        all_files = [self.sample+'_'+d+'.nxs' 
                    for d in os.listdir(self.sample_directory) 
                    if os.path.isdir(os.path.join(self.sample_directory, d))]
        filenames = sorted([f for f in all_files 
                    if os.path.exists(os.path.join(self.sample_directory, f))], 
                    key=natural_sort)
        for i, f in enumerate(filenames):
            scan = 'f%d' % i
            scans.append((scan, f, False))
        widget = NXWidget()
        widget.set_layout('stretch', 
                          self.checkboxes(*scans, vertical=True), 
                          'stretch')
        self.scroll_area = NXScrollArea(widget)
        self.insert_layout(2, self.scroll_area)

    @property
    def scan_list(self):
        scan_list = []
        for scan in self.checkbox:
            if self.checkbox[scan].isChecked():
                base_name = os.path.splitext(self.checkbox[scan].text())[0]
                scan_list.append(base_name.replace(self.sample+'_', ''))
        return ' '.join(scan_list)

    @property
    def scan_files(self):
        scan_files = []
        for scan in self.checkbox:
            if self.checkbox[scan].isChecked():
                scan_files.append(self.checkbox[scan].text())
        return scan_files

    def get_label(self, scan_file):
        base_name = os.path.basename(os.path.splitext(scan_file)[0])
        return base_name.replace(self.sample+'_', '')

    def select_scans(self):
        for scan in self.checkbox:
            self.checkbox[scan].setChecked(True)

    def clear_scans(self):
        for scan in self.checkbox:
            self.checkbox[scan].setChecked(False)

    def sum_scans(self):
        if not self.scan_files:
            raise NeXusError("No files selected")
        server = NXServer()
        scan_filter = ';;'.join(("NeXus Files (*.nxs)", "Any Files (*.* *)"))
        scan_prefix = self.scan_files[0][:self.scan_files[0].rindex('_')]
        preferred_name = os.path.join(self.sample_directory, 
                                      scan_prefix+'_sum.nxs')
        scan_file = getSaveFileName(self, 'Choose Summed File Name', 
                                    preferred_name, scan_filter)
        if not scan_file:
            return
        prefix = self.sample + '_'
        if not os.path.basename(scan_file).startswith(prefix):
            raise NeXusError("Summed file name must start with '%s'" % prefix)
        self.scan_label = self.get_label(scan_file)
        scan_dir = os.path.join(self.sample_directory, self.scan_label)
        reduce = NXReduce(directory=scan_dir)  
        for entry in reduce.entries:
            if self.checkbox['update'].isChecked():
                server.add_task('nxsum -d %s -e %s -u -s %s' 
                                % (scan_dir, entry, self.scan_list))
            else:
                server.add_task('nxsum -d %s -e %s -s %s' 
                                % (scan_dir, entry, self.scan_list))
