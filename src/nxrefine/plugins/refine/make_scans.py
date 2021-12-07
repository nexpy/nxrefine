# -----------------------------------------------------------------------------
# Copyright (c) 2015-2021, NeXpy Development Team.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file COPYING, distributed with this software.
# -----------------------------------------------------------------------------

import os
from operator import attrgetter

from nexpy.gui.datadialogs import GridParameters, NXDialog, NXWidget
from nexpy.gui.pyqt import getSaveFileName
from nexpy.gui.utils import natural_sort, report_error
from nexpy.gui.widgets import NXScrollArea
from nexusformat.nexus import nxload, NeXusError


def show_dialog():
    try:
        dialog = MakeDialog()
        dialog.show()
    except NeXusError as error:
        report_error("Making Scan Macro", error)


class MakeDialog(NXDialog):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.scans = None
        self.set_layout(
            self.directorybox("Choose Sample Directory", self.choose_sample),
            self.textboxes(('Scan Command', 'Pil2Mscan')),
            self.action_buttons(
                ('Select All', self.select_scans),
                ('Reverse All', self.reverse_scans),
                ('Clear All', self.clear_scans),
                ('Make Scan Macro', self.make_scans)),
            self.close_buttons(close=True))
        self.set_title('Make Scans')

    def choose_sample(self):
        super().choose_directory()
        self.sample_directory = self.get_directory()
        self.experiment_directory = os.path.dirname(
            os.path.dirname(self.sample_directory))
        self.macro_directory = os.path.join(
            self.experiment_directory, 'macros')
        self.label = os.path.basename(self.sample_directory)
        self.sample = os.path.basename(os.path.dirname(self.sample_directory))
        self.experiment = os.path.basename(self.experiment_directory)
        self.experiment_path = self.experiment
        self.scan_path = os.path.join(self.experiment, self.sample, self.label)
        self.setup_scans()

    def setup_scans(self):
        if self.scans:
            self.scans.delete_grid()
        self.scans = GridParameters()
        all_files = [self.sample+'_'+d+'.nxs'
                     for d in os.listdir(self.sample_directory)
                     if os.path.isdir(os.path.join(self.sample_directory, d))]
        filenames = sorted([f for f in all_files if os.path.exists(
            os.path.join(self.sample_directory, f))], key=natural_sort)
        for i, f in enumerate(filenames):
            scan = f'f{i}'
            self.scans.add(scan, i+1, f, True, self.update_scans)
            self.scans[scan].checkbox.stateChanged.connect(self.update_scans)
        scroll_widget = NXWidget()
        scroll_widget.set_layout(self.scans.grid(header=False))
        scroll_area = NXScrollArea(scroll_widget)
        scroll_area.setMinimumHeight(min(scroll_widget.sizeHint().height(),
                                         600))
        scroll_area.setWidgetResizable(True)
        self.insert_layout(2, scroll_area)

    @property
    def scan_list(self):
        scan_list = []
        for scan in self.scans.values():
            if scan.checkbox.isChecked() and scan.value > 0:
                scan_list.append(scan)
            else:
                scan.value = 0
        return sorted(scan_list, key=attrgetter('value'))

    def update_scans(self):
        scan_list = self.scan_list
        scan_number = 0
        for scan in scan_list:
            scan_number += 1
            scan.value = scan_number
        for scan in self.scans.values():
            if scan.checkbox.isChecked() and scan.value == 0:
                scan.value = scan_number + 1
                scan_number += 1

    def select_scans(self):
        for i, scan in enumerate(self.scans):
            self.scans[scan].value = i+1
            self.scans[scan].checkbox.setChecked(True)

    def reverse_scans(self):
        for i, scan in enumerate(reversed(self.scan_list)):
            scan.value = i+1
            scan.checkbox.setChecked(True)

    def clear_scans(self):
        for scan in self.scans:
            self.scans[scan].value = 0
            self.scans[scan].checkbox.setChecked(False)

    def make_scans(self):
        scans = [scan.label.text() for scan in self.scan_list]
        scan_command = self.textbox['Scan Command'].text()
        scan_parameters = ['#command path filename temperature detx dety ' +
                           'phi_start phi_step phi_end chi omega frame_rate']
        for scan in self.scan_list:
            nexus_file = scan.label.text()
            root = nxload(os.path.join(self.sample_directory, nexus_file))
            temperature = root.entry.sample.temperature
            base_name = os.path.basename(os.path.splitext(nexus_file)[0])
            scan_dir = base_name.replace(self.sample+'_', '')
            for entry in [root[e] for e in root if e != 'entry']:
                if 'phi_set' in entry['instrument/goniometer']:
                    phi_start = entry['instrument/goniometer/phi_set']
                else:
                    phi_start = entry['instrument/goniometer/phi']
                phi_step = entry['instrument/goniometer/phi'].attrs['step']
                phi_end = entry['instrument/goniometer/phi'].attrs['end']
                if 'chi_set' in entry['instrument/goniometer']:
                    chi = entry['instrument/goniometer/chi_set']
                else:
                    chi = entry['instrument/goniometer/chi']
                if 'omega_set' in entry['instrument/goniometer']:
                    omega = entry['instrument/goniometer/omega_set']
                else:
                    omega = entry['instrument/goniometer/omega']
                dx = entry['instrument/detector/translation_x']
                dy = entry['instrument/detector/translation_y']
                if ('frame_time' in entry['instrument/detector'] and
                        entry['instrument/detector/frame_time'] > 0.0):
                    frame_rate = 1.0 / entry['instrument/detector/frame_time']
                else:
                    frame_rate = 10.0
                scan_file = entry.nxname
                if scan_command == 'Pil2Mscan':
                    scan_parameters.append(
                        f'{scan_command} '
                        f'{os.path.join(self.scan_path, scan_dir)} '
                        f'{scan_file} {temperature:.6g} {dx:.6g} {dy:.6g} '
                        f'{phi_start:.6g} {phi_step:.6g} {phi_end:.6g} '
                        f'{chi:.6g} {omega:.6g} {frame_rate:.6g}')
            if scan_command == 'Pil2Mstring':
                scan_parameters.append(f'Pil2Mstring("{scan_dir}")')
            elif scan_command != 'Pil2Mscan':
                scan_parameters.append(f'{scan_command} {temperature}')
        if not os.path.exists(self.macro_directory):
            os.mkdir(os.path.join(self.experiment_directory, 'macros'))
        macro_filter = ';;'.join(("SPEC Macro (*.mac)", "Any Files (*.* *)"))
        macro = getSaveFileName(self, 'Open Macro', self.macro_directory,
                                macro_filter)
        if macro:
            with open(macro, 'w') as f:
                f.write('\n'.join(scan_parameters))
