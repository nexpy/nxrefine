from __future__ import unicode_literals
import os
import numpy as np
import timeit
from shutil import copyfile
from nexusformat.nexus import *
from nexpy.gui.datadialogs import BaseDialog
from nexpy.gui.utils import report_error, confirm_action, natural_sort
from nexpy.gui.pyqt import QtCore, getSaveFileName
from nxrefine.nxlock import Lock
from nxrefine.nxserver import NXServer


def show_dialog():
    try:
        dialog = SumDialog()
        dialog.show()
    except NeXusError as error:
        report_error("Summing Scans", error)


class SumDialog(BaseDialog):

    def __init__(self, parent=None):
        super(SumDialog, self).__init__(parent)
        self.scans = None
        self.set_layout(self.directorybox("Choose Sample Directory",
                                          self.choose_sample),
                        self.textboxes(('New Scan Label', '')),
                        self.action_buttons(('Select All', self.select_scans),
                                            ('Clear All', self.clear_scans),
                                            ('Sum Scans', self.sum_scans)),
                        self.close_layout(close=True))
        self.set_title('Sum Files')

    def choose_sample(self):
        super(SumDialog, self).choose_directory()
        self.sample_directory = self.get_directory()
        self.experiment_directory = os.path.dirname(os.path.dirname(self.sample_directory))
        self.label = os.path.basename(self.sample_directory)
        self.sample = os.path.basename(os.path.dirname(self.sample_directory))
        self.experiment = os.path.basename(self.experiment_directory)
        self.experiment_path = self.experiment
        self.scan_path = os.path.join(self.experiment, self.sample, self.label)
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
        self.checkbox_layout = self.checkboxes(*scans, vertical=True)
        self.insert_layout(2, self.checkbox_layout)

    @property
    def scan_list(self):
        scan_list = []
        for scan in self.checkbox:
            if self.checkbox[scan].isChecked():
                scan_list.append(self.checkbox[scan].text())
        return scan_list

    @property
    def scan_label(self):
        return self.textbox['New Scan Label'].text()

    def select_scans(self):
        for scan in self.checkbox:
            self.checkbox[scan].setChecked(True)

    def clear_scans(self):
        for scan in self.checkbox:
            self.checkbox[scan].setChecked(False)

    def sum_scans(self):
        server = NXServer(self.experiment_directory)
        if not server.is_running():
            raise NeXusError('Server not running')
        scan_dir = os.path.join(self.sample_directory, self.scan_label)
        scan_file = os.path.join(self.sample_directory, 
                                 self.sample+'_'+self.scan_label+'.nxs')
        if os.path.exists(scan_file):
            if confirm_action('New scan file already exists. Overwrite?'):
                os.remove(scan_file)
            else:
                return
        if os.path.exists(scan_dir):
            if not confirm_action(
                "New scan directory already exists. Overwrite?"):
                return
        else:
            os.mkdir(scan_dir)
        
        reduce = NXReduce(self.scan_path)    
        for entry in reduce.entries:
            server.add_task('nxsum -d %s -e %s -o' % (self.sample_directory,
                                                      entry))
