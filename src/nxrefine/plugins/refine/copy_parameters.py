# -----------------------------------------------------------------------------
# Copyright (c) 2022-2026, Argonne National Laboratory.
#
# Distributed under the terms of an Open Source License.
#
# The full license is in the file LICENSE.pdf, distributed with this software.
# -----------------------------------------------------------------------------

from nexpy.gui.dialogs import NXDialog
from nexpy.gui.utils import display_message, report_error
from nexusformat.nexus import NeXusError, NXdata, NXentry, nxopen
from nxrefine.nxparent import NXParent


def show_dialog():
    try:
        dialog = CopyDialog()
        dialog.show()
    except NeXusError as error:
        report_error("Copying Parameters", error)


class CopyDialog(NXDialog):

    def __init__(self, scans_file, subentry=None):
        super().__init__()
        self.parent = NXParent(scans_file, subentry=subentry)
        self.set_layout(self.filebox('Choose NeXus File'),
                        self.close_layout(save=True))
        self.set_title('Copying Parameters')
        self._selected = False

    def choose_file(self):
        super().choose_file(filter="Nexus Files (*.nxs)")
        self.nexus_file = self.get_filename()
        if self.nexus_file is None:
            return
        self.nexus_root = nxopen(self.nexus_file)
        if self.layout.count() == 2:
            self.insert_layout(1, self.checkboxes(
                ("settings", "Settings", True),
                ("sample", "Copy Sample", True),
                ("transform", "Transform", True),
                ("instrument", "Instrument", True)))

    @property
    def copy_settings(self):
        return self.checkbox['settings'].isChecked()

    @property
    def copy_sample(self):
        return self.checkbox['sample'].isChecked()

    @property
    def copy_transform(self):
        return self.checkbox['transform'].isChecked()

    @property
    def copy_instrument(self):
        return self.checkbox['instrument'].isChecked()

    def copy_file(self):
        entry = self.parent.entry.nxname
        scan_entry = self.parent.entry_path
        if self.copy_settings:
            if f'{scan_entry}/nxscans/settings' in self.nexus_root:
                settings = self.nexus_root[f'{scan_entry}/nxscans/settings']
            elif f'{entry}/nxscans/settings' in self.nexus_root:
                settings = self.nexus_root[f'{entry}/nxscans/settings']
            elif 'entry/nxreduce' in self.nexus_root:
                settings = self.nexus_root['entry/nxreduce']
            else:
                settings = {}
            for s in settings:
                self.parent.settings[s] = settings[s].nxvalue
        if self.copy_sample:
            if 'sample' in self.nexus_root[f'{entry}']:
                for s in self.nexus_root[f'{entry}/sample']:
                    self.parent.sample_info[s] = self.nexus_root[
                        f'{entry}/sample/{s}']
        if self.copy_transform:
            if 'transform' in self.nexus_root[f'{entry}']:
                transform = self.nexus_root[f'{entry}/transform']
            elif 'transform' in self.nexus_root[f'{entry}/nxscans']:
                transform = self.nexus_root[f'{entry}/nxscans/transform']
            else:
                display_message(f"No transform found in {self.nexus_file}")
                return
            H, K, L = transform['Qh'], transform['Qk'], transform['Ql']
            if self.parent.transform:
                del self.parent.scan_info['transform']
            self.parent.scan_info['transform'] = NXdata(axes=(L, K, H))
        if self.copy_instrument:
            for name in self.nexus_root.entries:
                if name == 'entry':
                    continue
                src = self.nexus_root[name]
                if (not isinstance(src, NXentry)
                        or 'instrument' not in src):
                    continue
                if name not in self.parent.root:
                    self.parent.root[name] = NXentry()
                dst = self.parent.root[name]
                if 'instrument' in dst:
                    del dst['instrument']
                dst['instrument'] = src['instrument']

    def accept(self):
        try:
            with self.parent.root:
                self.copy_file()
            self.parent.reload()
            super().accept()
        except NeXusError as error:
            report_error("Copying Parameters", error)
            super().reject()
