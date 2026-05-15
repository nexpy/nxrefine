# -----------------------------------------------------------------------------
# Copyright (c) 2026, Argonne National Laboratory.
#
# Distributed under the terms of an Open Source License.
#
# The full license is in the file LICENSE.pdf, distributed with this software.
# -----------------------------------------------------------------------------

from nexpy.gui.dialogs import GridParameters, NXDialog
from nexpy.gui.utils import confirm_action, report_error
from nexpy.gui.widgets import NXLabel, NXLineEdit, NXScrollArea, NXWidget

from nxrefine.nxparent import NXParent


class FilesDialog(NXDialog):

    def __init__(self, scans_file, entry=None):
        super().__init__()
        self.parent = NXParent(scans_file, entry=entry)

        layout = []

        if len(self.parent.scans) > 0:
            layout.append(NXLabel('Scan Files', bold=True, align='center'))
            self.scan_scroll_area = NXScrollArea()
            self.scan_files = GridParameters()
            for scan, selected in zip(self.parent.scans,
                                          self.parent.selected):
                filename = self.parent.scan_file(scan).name
                self.scan_files.add(scan, filename, '', selected)
            self.scan_widget = NXWidget()
            self.scan_widget.set_layout(self.make_layout(
            self.scan_files.grid(header=None, width=200, spacing=10)))
            self.scan_scroll_area.setWidget(self.scan_widget)
            layout.append(self.scan_scroll_area)
        else:
            self.scan_files = []
        
        if len(self.parent.other_scan_files) > 0:
            layout.append(NXLabel('Other Files', bold=True, align='center'))
            self.files_scroll_area = NXScrollArea()
            self.other_files = GridParameters()
            if len(self.parent.scans) == 0:
                default = True
            else:
                default = False
            for filename in self.parent.other_scan_files:
                self.other_files.add(filename.name, filename.name, '', default)
            self.files_widget = NXWidget()
            self.files_widget.set_layout(self.make_layout(
                self.other_files.grid(header=None, width=200, spacing=10)))
            self.files_scroll_area.setWidget(self.files_widget)
            layout.append(self.files_scroll_area)
            self.prefix_box = NXLineEdit()
            self.prefix_box.textChanged.connect(self.select_prefix)
            layout.append(self.make_layout(NXLabel('Prefix'),
                                           self.prefix_box))
        else:
            self.other_files = []
        self.set_layout(*layout, self.close_layout(save=True))
        self.set_title('Select Files')
        self.setMinimumWidth(400)

    def select_prefix(self):
        prefix = self.prefix_box.text()
        for f in self.other_files:
            if prefix:
                if self.other_files[f].value.startswith(prefix):
                    self.other_files[f].vary = True
                else:
                    self.other_files[f].vary = False
            else:
                self.other_files[f].vary = False

    def accept(self):
        try:
            with self.parent.root as root:
                scan_info = root[f'{self.parent.entry}/nxscans']
                for f in self.scan_files:
                    if self.scan_files[f].vary:
                        scan_info['selected'][self.parent.index(f)] = True
                    else:
                        scan_info['selected'][self.parent.index(f)] = False
            for i, f in enumerate(self.other_files):
                if self.other_files[f].vary:
                    other_file = self.other_files[f].name
                    if self.parent.has_parent(other_file):
                        if confirm_action('Overwrite Parent?',
                            f'File {other_file} already has a parent.'):
                            self.parent.add_scan(other_file, selected=True)
                    else:
                        self.parent.add_scan(other_file, selected=True)
            self.parent.update_scan_data()
            self.parent.reload()
            super().accept()
        except Exception as error:
            report_error("Selecting Scan Files", error)
            self.parent.reload()
            super().reject()
