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
from nxrefine.nxreduce import NXReduce


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
                        self.action_buttons(('Select All', self.select_scans),
                                            ('Clear All', self.clear_scans),
                                            ('Sum Scans', self.sum_scans)),
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
        self.checkbox_layout = self.checkboxes(*scans, vertical=True)
        self.insert_layout(2, self.checkbox_layout)

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
        server = NXServer(self.experiment_directory)
        if not server.is_running():
            raise NeXusError('Server not running')
        scan_filter = ';;'.join(("NeXus Files (*.nxs)", "Any Files (*.* *)"))
        preferred_name = os.path.join(self.sample_directory, 
                                      self.sample+'_'+'sum.nxs')
        scan_file = getSaveFileName(self, 'Choose Summed File Name', 
                                    preferred_name, scan_filter)
        if not scan_file:
            return
        prefix = self.sample + '_'
        if not os.path.basename(scan_file).startswith(prefix):
            raise NeXusError("Summed file name must start with '%s'" % prefix)

        self.scan_label = self.get_label(scan_file)
        scan_dir = os.path.join(self.sample_directory, self.scan_label)
        scan_file = os.path.join(self.sample_directory, 
                                 self.sample+'_'+self.scan_label+'.nxs')
        copy_file = os.path.join(self.sample_directory, self.scan_files[0])
        if os.path.exists(scan_dir):
            if not confirm_action(
                "New scan directory already exists. Overwrite?"):
                return
        else:
            os.mkdir(scan_dir)
        copyfile(copy_file, scan_file)
        self.clean_scan(scan_file)
        self.treeview.tree.load(scan_file, 'rw')
        reduce = NXReduce(directory=scan_dir)    
        for entry in reduce.entries:
            server.add_task('nxsum -d %s -e %s -o -s %s' 
                            % (self.sample_directory, entry, self.scan_list))

    def clean_scan(self, scan_file):
        with Lock(scan_file):
            scan_root = nxload(scan_file, 'rw')
            for entry in scan_root:
                if 'transform' in scan_root[entry]:
                    del scan_root[entry]['transform']
                if 'masked_transform' in scan_root[entry]:
                    del scan_root[entry]['masked_transform']
                if 'nxtransform' in scan_root[entry]:
                    del scan_root[entry]['nxtransform']
                if 'nxcombine' in scan_root[entry]:
                    del scan_root[entry]['nxcombine']
                if 'nxmasked_transform' in scan_root[entry]:
                    del scan_root[entry]['nxmasked_transform']
                if 'nxmasked_combine' in scan_root[entry]:
                    del scan_root[entry]['nxmasked_combine']
                if 'data' in scan_root[entry]:
                    if 'data' in scan_root[entry]['data']:
                        del scan_root[entry]['data/data']
                        scan_root[entry]['data/data'] = NXlink(
                            '/entry/data/data', self.scan_label+'/'+entry+'.h5')
                    if 'data_mask' in scan_root[entry]['data']:
                        del scan_root[entry]['data/data_mask']
