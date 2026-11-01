# -----------------------------------------------------------------------------
# Copyright (c) 2018-2026, Argonne National Laboratory.
#
# Distributed under the terms of an Open Source License.
#
# The full license is in the file LICENSE.pdf, distributed with this software.
# -----------------------------------------------------------------------------

from nexpy.gui.dialogs import NXDialog
from nexpy.gui.pyqt import QtCore, QtWidgets, getSaveFileName
from nexpy.gui.utils import display_message, report_error
from nexusformat.nexus import NeXusError

from nxrefine.nxbeamline import get_beamline
from nxrefine.nxparent import NXParent
from nxrefine.nxsettings import NXSettings


def show_dialog():
    try:
        dialog = MacroDialog()
        dialog.show()
    except NeXusError as error:
        report_error("Making Scan Macro", error)


class MacroDialog(NXDialog):

    def __init__(self, parent=None):
        super().__init__(parent)

        self.scan_list = None
        self.macro_layouts = False

        self.set_layout(self.filebox('Choose Parent File'),
                        self.close_layout(close=True))
        self.set_title('Making Scan Macro')

    def choose_file(self):
        super().choose_file(filter="Parent Files (*_scans.nxs)")
        self.parent_file = self.get_filename()
        if self.parent_file is None:
            return
        try:
            self.parent = NXParent(self.parent_file)
            if not self.parent.scans_defined:
                raise NeXusError(
                    f"'{self.parent.name}' does not contain a list of scans")
            instrument = NXSettings(
                self.parent.experiment_directory).settings[
                    'instrument']['instrument']
            beamline = get_beamline(instrument)
            if not beamline.create_macro_enabled:
                raise NeXusError("Making scan macros not implemented for "
                                 f"{beamline.name}")
            self.beamline = beamline(directory=self.parent.directory)
        except NeXusError as error:
            report_error("Making Scan Macro", error)
            return
        self.macro_directory = self.parent.experiment_directory / 'macros'
        self.setup_scans()

    def setup_scans(self):
        if self.scan_list is None:
            self.scan_list = QtWidgets.QListWidget()
            self.scan_list.setDragDropMode(
                QtWidgets.QAbstractItemView.InternalMove)
            self.scan_list.setDefaultDropAction(QtCore.Qt.MoveAction)
            self.scan_list.setSelectionMode(
                QtWidgets.QAbstractItemView.SingleSelection)
            self.scan_list.setMinimumHeight(300)
        self.scan_list.clear()
        for scan, selected in zip(self.parent.scans, self.parent.selected):
            item = QtWidgets.QListWidgetItem(
                self.parent.scan_directory(scan))
            item.setData(QtCore.Qt.UserRole, scan)
            item.setFlags(item.flags() | QtCore.Qt.ItemIsUserCheckable)
            item.setCheckState(
                QtCore.Qt.Checked if selected else QtCore.Qt.Unchecked)
            self.scan_list.addItem(item)
        if not self.macro_layouts:
            self.insert_layout(1, self.textboxes(('Scan Command',
                                                  'Pil2Mscan')))
            self.insert_layout(2, self.make_layout(self.scan_list))
            self.insert_layout(3, self.action_buttons(
                ('Move Up', self.move_up),
                ('Move Down', self.move_down),
                ('Select All', self.select_scans),
                ('Reverse All', self.reverse_scans),
                ('Clear All', self.clear_scans)))
            self.insert_layout(4, self.action_buttons(
                ('Make Scan Macro', self.create_macro)))
            self.macro_layouts = True
            self.setMinimumWidth(500)

    @property
    def items(self):
        return [self.scan_list.item(row)
                for row in range(self.scan_list.count())]

    @property
    def checked_scans(self):
        return [item.data(QtCore.Qt.UserRole) for item in self.items
                if item.checkState() == QtCore.Qt.Checked]

    def move_item(self, offset):
        row = self.scan_list.currentRow()
        new_row = row + offset
        if row < 0 or new_row < 0 or new_row >= self.scan_list.count():
            return
        item = self.scan_list.takeItem(row)
        self.scan_list.insertItem(new_row, item)
        self.scan_list.setCurrentRow(new_row)

    def move_up(self):
        self.move_item(-1)

    def move_down(self):
        self.move_item(1)

    def select_scans(self):
        for item in self.items:
            item.setCheckState(QtCore.Qt.Checked)

    def reverse_scans(self):
        items = [self.scan_list.takeItem(0)
                 for _ in range(self.scan_list.count())]
        for item in reversed(items):
            self.scan_list.addItem(item)

    def clear_scans(self):
        for item in self.items:
            item.setCheckState(QtCore.Qt.Unchecked)

    def create_macro(self):
        scans = self.checked_scans
        if not scans:
            display_message("Making Scan Macro", "No scans selected")
            return
        try:
            scan_command = self.textbox['Scan Command'].text()
            scan_files = [self.parent.scan_file(scan) for scan in scans]
            scan_parameters = self.beamline.create_macro(scan_files,
                                                         scan_command)
            self.macro_directory.mkdir(exist_ok=True)
            macro_filter = ';;'.join(("SPEC Macro (*.mac)",
                                      "Any Files (*.* *)"))
            default_name = (self.macro_directory /
                            f"{self.parent.sample}_{self.parent.label}.mac")
            macro = getSaveFileName(self, 'Save Macro', str(default_name),
                                    macro_filter)
            if macro:
                with open(macro, 'w') as f:
                    f.write('\n'.join(scan_parameters) + '\n')
                self.status_message.setText(f"Saved macro '{macro}'")
        except Exception as error:
            report_error("Making Scan Macro", error)
