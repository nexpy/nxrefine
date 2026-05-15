# -----------------------------------------------------------------------------
# Copyright (c) 2022-2026, Argonne National Laboratory.
#
# Distributed under the terms of an Open Source License.
#
# The full license is in the file LICENSE.pdf, distributed with this software.
# -----------------------------------------------------------------------------
from nexpy.gui.dialogs import NXDialog
from nexpy.gui.utils import report_error
from nexpy.gui.widgets import NXLabel, NXPushButton
from nexusformat.nexus import NeXusError

from nxrefine.nxparent import NXParent
from nxrefine.nxreduce import NXMultiReduce
from nxrefine.plugins.refine.copy_parameters import CopyDialog
from nxrefine.plugins.refine.define_lattice import LatticeDialog
from nxrefine.plugins.refine.edit_parameters import ParametersDialog
from nxrefine.plugins.refine.select_files import FilesDialog
from nxrefine.plugins.refine.transform_data import TransformDialog


def show_dialog():
    try:
        dialog = InitializeDialog()
        dialog.show()
    except NeXusError as error:
        report_error("Initialize Scans", error)


class InitializeDialog(NXDialog):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.set_layout(self.filebox('Choose Parent File'),
                        self.close_layout(close=True))
        self.set_title('Initialize Scans')

    def choose_file(self):
        super().choose_file(filter="Parent Files (*_scans.nxs)")
        self.parent_file = self.get_filename()
        if self.parent_file is None:
            return
        self.parent = NXParent(self.parent_file)
        self.entries = [self.parent.root[entry]
                        for entry in self.parent.root if entry[-1].isdigit()]
        self.reduce = NXMultiReduce(self.parent.root)
        if self.layout.count() == 2:
            self.insert_layout(1, self.subentry_layout())
            self.layout.insertLayout(2, self.action_buttons(
                ('Select Files', self.setup_files),
                ('Edit Settings', self.setup_settings),
                ('Define Lattice', self.setup_lattice),
                ('Setup Transforms', self.setup_transforms),
                ('Copy NeXus File', self.copy_parameters)))

    @property
    def subentry(self):
        return self.subentry_combo.selected

    def subentry_layout(self):
        self.subentry_combo = self.select_box(self.parent.scan_entries,
                                              default=self.parent.entry,
                                              slot=self.select_subentry)
        sub_button = NXPushButton('Create New Subentry', self.create_subentry)
        return self.make_layout(NXLabel('Subentry:'), self.subentry_combo,
                                'stretch', sub_button)

    def refresh_subentries(self):
        self.subentry_combo.blockSignals(True)
        current = self.subentry_combo.selected
        self.subentry_combo.clear()
        self.subentry_combo.add(*self.parent.scan_entries)
        if current in self.parent.scan_entries:
            self.subentry_combo.select(current)
        self.subentry_combo.blockSignals(False)

    def select_subentry(self):
        self.parent.entry = self.subentry

    def create_subentry(self):
        name = self.input_text('New Subentry', 'Enter subentry name:')
        if name is None:
            return
        self.parent.create_scan_entry(name)
        self.refresh_subentries()
        self.subentry_combo.select(f'/entry/{name}')
        self.parent.reload()

    def setup_files(self):
        dialog = FilesDialog(self.parent.filename, self.parent.subentry)
        dialog.show()
        pass

    def setup_settings(self):
        dialog = ParametersDialog(self.parent.filename, self.parent.subentry)
        dialog.show()

    def setup_lattice(self):
        dialog = LatticeDialog(self.parent.filename, self.parent.subentry)
        dialog.show()

    def setup_transforms(self):
        dialog = TransformDialog(self.parent.filename, self.parent.subentry)
        dialog.show()

    def copy_parameters(self):
        dialog = CopyDialog(self.parent.filename, self.parent.subentry)
        dialog.show()
