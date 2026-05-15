# -----------------------------------------------------------------------------
# Copyright (c) 2015-2026, Argonne National Laboratory.
#
# Distributed under the terms of an Open Source License.
#
# The full license is in the file LICENSE.pdf, distributed with this software.
# -----------------------------------------------------------------------------

from pathlib import Path

from nexpy.gui.dialogs import NXDialog
from nexpy.gui.utils import confirm_action, report_error
from nexpy.gui.widgets import NXLabel, NXLineEdit
from nexusformat.nexus import NeXusError, NXfield, NXlink, nxopen

from nxrefine.nxparent import NXParent


def show_dialog():
    try:
        dialog = ScanDialog()
        dialog.show()
    except NeXusError as error:
        report_error("Creating Scan", error)


class ScanDialog(NXDialog):

    def __init__(self, parent=None):
        super().__init__(parent)

        self.positions = 1
        self.entries = {}

        self.set_layout(self.filebox('Choose Parent File'),
                        self.close_layout(close=True))
        self.set_title('Creating New Scan(s)')

    def choose_file(self):
        super().choose_file(filter="Parent Files (*_scans.nxs)")
        self.parent_file = self.get_filename()
        if self.parent_file is None:
            return

        self.parent = NXParent(self.parent_file)
        self.scan_path = self.parent.scan_path
        self.scan_units = self.parent.scan_units

        self.scan_box = NXLineEdit('300', align='right', slot=self.update_scan)
        self.scan_layout = self.make_layout(NXLabel(self.scan_label),
                                            self.scan_box,
                                            NXLabel(self.scan_units))
        self.insert_layout(1, self.scan_layout)
        self.scandir_box = NXLineEdit('', align='right')
        self.scandir_layout = self.make_layout(NXLabel('Scan Directory'),
                                               self.scandir_box)
        self.update_scan()
        self.insert_layout(2, self.scandir_layout) 
        self.insert_layout(3, self.action_buttons(('Make Scan File',
                                                   self.make_scan)))

    @property
    def directory(self):
        return self.parent.directory

    @property
    def sample(self):
        return self.parent.sample

    @property
    def label(self):
        return self.parent.label

    @property
    def experiment_directory(self):
        return self.parent.experiment_directory

    @property
    def task_directory(self):
        return self.parent.task_directory

    @property
    def scan_value(self):
        try:
            return float(self.scan_box.text())
        except ValueError:
            return self.scan_box.text()

    @property
    def scan_directory(self):
        return self.scandir_box.text()

    @scan_directory.setter
    def scan_directory(self, value):
        self.scandir_box.setText(value)

    @property
    def scan_label(self):
        if self.scan_path:
            return Path(self.scan_path).name.replace('_', ' ').title()
        else:
            return 'Scan Value'

    @property
    def scan_file(self):
        return self.sample + '_' + self.scandir_box.text() + '.nxs'

    @property
    def scan_selected(self):
        return (self.scan_directory
                == self.parent.get_scan_directory(self.scan_value))

    def update_scan(self):
        self.scan_directory = self.parent.get_scan_directory(self.scan_value)

    def create_scan(self):
        self.directory.joinpath(self.scan_directory).mkdir(exist_ok=True)
        with nxopen(self.directory / self.scan_file, 'w') as root:
            for entry in self.parent.root.entries:
                root[entry] = self.parent.root[entry]
                if entry != 'entry':
                    data_link = root[f"{entry}/data/data"]
                    _target, _filename = data_link._target, data_link._filename
                    _filename = Path(self.scan_directory).joinpath(_filename)
                    del root[f"{entry}/data/data"]
                    root[f"{entry}/data/data"] = NXlink(_target, _filename)
            root[self.scan_path] = NXfield(self.scan_value,
                                           units=self.scan_units)
        self.parent.add_scan(self.scan_file, selected=self.scan_selected)

    def reload(self):
        try:
            self.tree[self.tree.node_from_file(self.scan_file)].reload()
        except Exception:
            pass

    def make_scan(self):
        scan_file = self.parent.directory / self.scan_file
        if scan_file.exists() and not confirm_action(
                "Overwrite existing scan file?",
                f"'{scan_file}' already exists."):
            return
        self.create_scan()
        new_scan_path = scan_file.relative_to(self.experiment_directory.parent)
        self.status_message.setText(f"Created scan file '{new_scan_path}'")
        self.reload()
        self.parent.reload()
