# -----------------------------------------------------------------------------
# Copyright (c) 2015-2021, NeXpy Development Team.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file COPYING, distributed with this software.
# -----------------------------------------------------------------------------

import os

import numpy as np
from nexpy.gui.datadialogs import NXDialog
from nexpy.gui.pyqt import QtGui, QtWidgets
from nexpy.gui.utils import report_error
from nexpy.gui.widgets import NXLabel, NXLineEdit
from nexusformat.nexus import NeXusError
from nxrefine.nxrefine import NXRefine


def show_dialog():
    try:
        dialog = TransformDialog()
        dialog.show()
    except NeXusError as error:
        report_error("Preparing Data Transform", error)


class TransformDialog(NXDialog):

    def __init__(self, parent=None):
        super().__init__(parent)

        self.select_entry(self.choose_entry)

        self.Qgrid = QtWidgets.QGridLayout()
        self.Qgrid.setSpacing(10)
        headers = ['Axis', 'Q', 'dQ', 'N', 'Max']
        width = [25, 50, 50, 25, 50]
        column = 0
        for header in headers:
            label = NXLabel(header, bold=True, align='center')
            self.Qgrid.addWidget(label, 0, column)
            self.Qgrid.setColumnMinimumWidth(column, width[column])
            column += 1
        self.Qbox = {}
        self.dQbox = {}
        self.Nbox = {}
        self.maxbox = {}
        for i, label in enumerate(['H', 'K', 'L']):
            self.Qgrid.addWidget(NXLabel(label, align='center'), i+1, 0)
            self.Qbox[label] = NXLineEdit(slot=self.calculate, width=100,
                                          align='right')
            self.Qgrid.addWidget(self.Qbox[label], i+1, 1)
            self.dQbox[label] = NXLineEdit(slot=self.calculate, width=100,
                                           align='right')
            self.Qgrid.addWidget(self.dQbox[label], i+1, 2)
            self.Nbox[label] = NXLabel(align='center')
            self.Qgrid.addWidget(self.Nbox[label], i+1, 3)
            self.maxbox[label] = NXLabel(align='center')
            self.Qgrid.addWidget(self.maxbox[label], i+1, 4)
        self.set_layout(self.entry_layout, self.close_buttons(save=True))
        self.setWindowTitle('Transforming Data')
        try:
            self.initialize_grid()
        except Exception:
            pass

    def choose_entry(self):
        try:
            refine = NXRefine(self.entry)
            if refine.xp is None:
                raise NeXusError("No peaks in entry")
        except NeXusError as error:
            report_error("Refining Lattice", error)
            return
        self.refine = refine
        if self.layout.count() == 2:
            self.insert_layout(1, self.Qgrid)
            self.insert_layout(2, self.checkboxes(
                ('copy', 'Copy to all entries', True),
                ('mask', 'Create masked transforms', True),
                ('overwrite', 'Overwrite transforms', False)))
        self.refine.initialize_grid()
        self.update_grid()

    def update_grid(self):
        self.Qbox['H'].setText(f"{self.refine.h_stop:g}")
        self.Qbox['K'].setText(f"{self.refine.k_stop:g}")
        self.Qbox['L'].setText(f"{self.refine.l_stop:g}")
        self.dQbox['H'].setText(f"{self.refine.h_step:g}")
        self.dQbox['K'].setText(f"{self.refine.k_step:g}")
        self.dQbox['L'].setText(f"{self.refine.l_step:g}")
        self.Nbox['H'].setText(f"{self.refine.h_shape:g}")
        self.Nbox['K'].setText(f"{self.refine.k_shape:g}")
        self.Nbox['L'].setText(f"{self.refine.l_shape:g}")
        self.maxbox['H'].setText(f"{self.refine.Qmax / self.refine.astar:g}")
        self.maxbox['K'].setText(f"{self.refine.Qmax / self.refine.bstar:g}")
        self.maxbox['L'].setText(f"{self.refine.Qmax / self.refine.cstar:g}")

    def calculate(self):
        for label, rlu in [('H', self.refine.astar),
                           ('K', self.refine.bstar),
                           ('L', self.refine.cstar)]:
            self.Nbox[label].setText(
                int(np.round(2 * float(self.Qbox[label].text()) /
                             float(self.dQbox[label].text()), 2)) + 1)
            self.maxbox[label].setText(f"{self.refine.Qmax / rlu:g}")

    def get_output_file(self, mask=False, entry=None):
        if entry is None:
            entry = self.entry
        if mask:
            return os.path.splitext(
                entry.data.nxsignal.nxfilename)[0] + '_masked_transform.nxs'
        else:
            return os.path.splitext(
                entry.data.nxsignal.nxfilename)[0] + '_transform.nxs'

    def get_settings_file(self, entry=None):
        if entry is None:
            entry = self.entry
        return os.path.splitext(
            entry.data.nxsignal.nxfilename)[0] + '_transform.pars'

    def get_parameters(self, Q):
        stop, step = float(self.Qbox[Q].text()), float(self.dQbox[Q].text())
        return -stop, step, stop

    def write_parameters(self, output_file, settings_file):
        self.refine.output_file = output_file
        self.refine.settings_file = settings_file
        self.refine.h_start, self.refine.h_step, self.refine.h_stop = (
            self.get_parameters('H'))
        self.refine.k_start, self.refine.k_step, self.refine.k_stop = (
            self.get_parameters('K'))
        self.refine.l_start, self.refine.l_step, self.refine.l_stop = (
            self.get_parameters('L'))
        self.refine.define_grid()

    @property
    def copy(self):
        return self.checkbox['copy'].isChecked()

    @property
    def mask(self):
        return self.checkbox['mask'].isChecked()

    @property
    def overwrite(self):
        return self.checkbox['overwrite'].isChecked()

    def accept(self):
        try:
            if 'transform' in self.entry and not self.overwrite:
                self.display_message(
                    "Preparing Transform",
                    f"Transform group already exists in {self.entry.nxname}")
                return
            if (self.mask and 'masked_transform' in self.entry
                    and not self.overwrite):
                self.display_message(
                    "Preparing Transform",
                    "Masked transform group already exists in "
                    f"{self.entry.nxname}")
                return
            output_file = self.get_output_file()
            settings_file = self.get_settings_file()
            self.write_parameters(output_file, settings_file)
            self.refine.prepare_transform(output_file)
            if self.mask:
                masked_output_file = self.get_output_file(mask=True)
                self.refine.prepare_transform(masked_output_file, mask=True)
            self.refine.write_settings(settings_file)
            if self.copy:
                root = self.entry.nxroot
                for entry in [e for e in root
                              if e != 'entry' and e != self.entry.nxname]:
                    if 'transform' in root[entry] and not self.overwrite:
                        self.display_message(
                            "Preparing Transform",
                            f"Transform group already exists in {entry}")
                        return
                    if (self.mask and 'masked_transform' in root[entry]
                            and not self.overwrite):
                        self.display_message(
                            "Preparing Transform",
                            f"Masked transform group already exists in {entry}"
                            )
                        return
                    self.refine = NXRefine(root[entry])
                    output_file = self.get_output_file(entry=root[entry])
                    settings_file = self.get_settings_file(entry=root[entry])
                    self.write_parameters(output_file, settings_file)
                    self.refine.prepare_transform(output_file)
                    if self.mask:
                        masked_output_file = self.get_output_file(
                            mask=True, entry=root[entry])
                        self.refine.prepare_transform(
                            masked_output_file, mask=True)
                    self.refine.write_settings(settings_file)
            super().accept()
        except NeXusError as error:
            report_error("Preparing Data Transform", error)
