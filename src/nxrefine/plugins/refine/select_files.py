# -----------------------------------------------------------------------------
# Copyright (c) 2026, Argonne National Laboratory.
#
# Distributed under the terms of an Open Source License.
#
# The full license is in the file LICENSE.pdf, distributed with this software.
# -----------------------------------------------------------------------------

import threading

from nexpy.gui.dialogs import GridParameters, NXDialog
from nexpy.gui.utils import confirm_action, report_error
from nexpy.gui.widgets import (NXLabel, NXLineEdit, NXPushButton, NXScrollArea,
                               NXWidget)
from qtpy import QtCore

from nxrefine.nxparent import NXParent

# Keeps ScanDataWorker instances alive until their background thread finishes.
_active_workers = set()


class ScanDataWorker(QtCore.QObject):
    """Run NXParent.update_scan_data() on a daemon thread.

    Lives independently of the FilesDialog so the dialog can close
    immediately while the (potentially slow) consolidation continues.
    A Qt signal is emitted on completion so that reload() is called on
    the main thread via the event loop.
    """

    finished = QtCore.Signal()

    def __init__(self, nxparent):
        super().__init__()
        self._parent = nxparent
        _active_workers.add(self)
        self.finished.connect(nxparent.reload)
        self.finished.connect(lambda: _active_workers.discard(self))

    def start(self):
        threading.Thread(target=self._run, daemon=True).start()

    def _run(self):
        self._parent.update_scan_data()
        self.finished.emit()


class FilesDialog(NXDialog):

    def __init__(self, scans_file, subentry=None):
        super().__init__()
        self.parent = NXParent(scans_file, subentry=subentry)

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
            layout.append(self.make_layout(
                NXPushButton('Select All', self.select_all),
                NXPushButton('Deselect All', self.deselect_all),
                align='center'))
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

    def select_all(self):
        for f in self.scan_files:
            self.scan_files[f].vary = True

    def deselect_all(self):
        for f in self.scan_files:
            self.scan_files[f].vary = False

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
                scan_info = root[f'{self.parent.entry_path}/nxscans']
                for f in self.scan_files:
                    if self.scan_files[f].vary:
                        scan_info['selected'][self.parent.index(f)] = True
                    else:
                        scan_info['selected'][self.parent.index(f)] = False
            for i, f in enumerate(self.other_files):
                if self.other_files[f].vary:
                    other_file = self.other_files[f].name
                    if self.parent.is_parent(other_file):
                        self.parent.add_scan(other_file, selected=True)
                    elif self.parent.has_parent(other_file):
                        if confirm_action('Overwrite Parent?',
                            f'File {other_file} already has a parent.'):
                            self.parent.add_scan(other_file, selected=True)
                    else:
                        self.parent.add_scan(other_file, selected=True)
            super().accept()
            ScanDataWorker(self.parent).start()
        except Exception as error:
            report_error("Selecting Scan Files", error)
            self.parent.reload()
            super().reject()
