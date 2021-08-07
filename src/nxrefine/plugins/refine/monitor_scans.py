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
from nxrefine.nxreduce import NXMultiReduce


def show_dialog():
    try:
        dialog = MonitorDialog()
        dialog.show()
    except NeXusError as error:
        report_error("Monitoring Scans", error)


class MonitorDialog(NXDialog):

    def __init__(self, parent=None):
        super(MonitorDialog, self).__init__(parent)
        monitors = ['Beam Current', 'Undulator Current'  
                    'Monitor 1', 'Monitor 2']
        self.monitor_combo = self.select_box(monitors)
        self.set_layout(self.directorybox("Choose Sample Directory",
                                          self.choose_sample),
                        self.make_layout(self.action_buttons(('Plot Monitors', self.plot_monitors)),
                                         self.monitor_combo),
                        self.close_layout(close=True))
        self.set_title('Monitor Scans')

    def choose_sample(self):
        super(MonitorDialog, self).choose_directory()
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
        scans = []
        for scan in self.scan_boxes:
            if self.checkbox[scan].isChecked():
                base_name = os.path.splitext(self.checkbox[scan].text())[0]
                scans.append(base_name.replace(self.sample+'_', ''))
        return scans

    @property
    def scan_files(self):
        scan_files = []
        for scan in self.scan_boxes:
            if self.checkbox[scan].isChecked():
                scan_files.append(self.checkbox[scan].text())
        return scan_files

    def get_label(self, scan_file):
        base_name = os.path.basename(os.path.splitext(scan_file)[0])
        return base_name.replace(self.sample+'_', '')

    def select_scans(self):
        for scan in self.scan_boxes:
            self.checkbox[scan].setChecked(True)

    def clear_scans(self):
        for scan in self.scan_boxes:
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
        reduce = NXMultiReduce(directory=scan_dir, overwrite=True)
        reduce.nxsum(self.scan_list)
        self.treeview.tree.load(scan_file, 'rw')
        command = 'nxsum -d {}'.format(scan_dir)
        if self.update:
            command += ' -u'
        if self.overwrite:
            command += ' -o'
        for entry in reduce.entries:
            server.add_task('{} -e {} -s {}'.format(command, entry,
                                                    ' '.join(self.scan_list)))
