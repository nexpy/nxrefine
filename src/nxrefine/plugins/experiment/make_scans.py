# -----------------------------------------------------------------------------
# Copyright (c) 2022, Argonne National Laboratory.
#
# Distributed under the terms of an Open Source License.
#
# The full license is in the file LICENSE.pdf, distributed with this software.
# -----------------------------------------------------------------------------

from operator import attrgetter
from pathlib import Path

from nexpy.gui.pyqt import getSaveFileName
from nexpy.gui.utils import display_message, natural_sort, report_error
from nexpy.gui.widgets import GridParameters, NXDialog, NXScrollArea, NXWidget
from nexusformat.nexus import NeXusError

from nxrefine.nxbeamline import get_beamline
from nxrefine.nxsettings import NXSettings


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
        self.scan_path = Path(self.get_directory())
        instrument = NXSettings(
            self.scan_path.parent.parent).settings['instrument']['instrument']
        self.beamline = get_beamline(instrument)
        if not self.beamline.make_scans_enabled:
            display_message(
                "Making Scans",
                f"Making scan macros not implemented for {self.beamline.name}")
            self.reject()
        self.macro_directory = self.scan_path.parent.parent / 'macros'
        self.sample = self.scan_path.parent.name
        self.setup_scans()

    def setup_scans(self):
        if self.scans:
            self.scans.delete_grid()
        self.scans = GridParameters()
        all_files = [self.sample+'_'+str(d)+'.nxs'
                     for d in self.scan_path.iterdir() if d.is_dir()]
        filenames = sorted([str(f) for f in all_files if
                            self.scan_path.joinpath(f).exists()],
                           key=natural_sort)
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
        scan_command = self.textbox['Scan Command'].text()
        scan_files = [Path(f) for f in self.scan_list]
        scan_parameters = self.beamline.make_scans(scan_files, scan_command)
        self.macro_directory.mkdir(exists_ok=True)
        macro_filter = ';;'.join(("SPEC Macro (*.mac)", "Any Files (*.* *)"))
        macro = getSaveFileName(self, 'Open Macro', self.macro_directory,
                                macro_filter)
        if macro:
            with open(macro, 'w') as f:
                f.write('\n'.join(scan_parameters))
