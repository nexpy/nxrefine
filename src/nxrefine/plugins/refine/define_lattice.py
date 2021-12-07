# -----------------------------------------------------------------------------
# Copyright (c) 2015-2021, NeXpy Development Team.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file COPYING, distributed with this software.
# -----------------------------------------------------------------------------

import os

import iotbx.cif as cif
from cctbx import sgtbx
from nexpy.gui.datadialogs import GridParameters, NXDialog
from nexpy.gui.pyqt import getOpenFileName
from nexpy.gui.utils import report_error
from nexpy.gui.widgets import NXCheckBox, NXPushButton
from nexusformat.nexus import NeXusError
from nxrefine.nxrefine import NXRefine


def show_dialog():
    try:
        dialog = LatticeDialog()
        dialog.show()
    except NeXusError as error:
        report_error("Defining Lattice", error)


class LatticeDialog(NXDialog):

    def __init__(self, parent=None):
        super().__init__(parent)

        self.select_root(self.choose_entry)

        self.refine = NXRefine()

        self.parameters = GridParameters()
        self.parameters.add('space_group', self.refine.space_group,
                            'Space Group', slot=self.set_groups)
        self.parameters.add('laue_group', self.refine.laue_groups,
                            'Laue Group')
        self.parameters.add('symmetry', self.refine.symmetries, 'Symmetry',
                            slot=self.set_lattice_parameters)
        self.parameters.add('centring', self.refine.centrings, 'Cell Centring')
        self.parameters.add('a', self.refine.a, 'Unit Cell - a (Ang)',
                            slot=self.set_lattice_parameters)
        self.parameters.add('b', self.refine.b, 'Unit Cell - b (Ang)',
                            slot=self.set_lattice_parameters)
        self.parameters.add('c', self.refine.c, 'Unit Cell - c (Ang)',
                            slot=self.set_lattice_parameters)
        self.parameters.add('alpha', self.refine.alpha,
                            'Unit Cell - alpha (deg)',
                            slot=self.set_lattice_parameters)
        self.parameters.add('beta', self.refine.beta,
                            'Unit Cell - beta (deg)',
                            slot=self.set_lattice_parameters)
        self.parameters.add('gamma', self.refine.gamma,
                            'Unit Cell - gamma (deg)',
                            slot=self.set_lattice_parameters)
        self.parameters['laue_group'].value = self.refine.laue_group
        self.parameters['symmetry'].value = self.refine.symmetry
        self.parameters['centring'].value = self.refine.centring
        self.import_button = NXPushButton('Import CIF', self.import_cif)
        self.import_checkbox = NXCheckBox('Update Lattice Parameters')
        self.set_layout(self.root_layout, self.close_buttons(save=True))
        self.set_title('Defining Lattice')

    def choose_entry(self):
        self.refine = NXRefine(self.root['entry'])
        if self.layout.count() == 2:
            self.insert_layout(1, self.parameters.grid(header=False))
            if sgtbx:
                self.insert_layout(2, self.make_layout(self.import_button,
                                                       self.import_checkbox,
                                                       align='center'))
        self.update_parameters()

    def import_cif(self):
        filename = getOpenFileName(self, 'Open CIF File')
        if os.path.exists(filename):
            cif_info = cif.reader(file_path=filename).model()
            for c in cif_info:
                s = cif_info[c]
                if '_cell_length_a' in s:
                    break

            def value(text):
                if '(' in text:
                    return float(text[:text.index('(')])
                else:
                    return float(text)

            if self.import_checkbox.isChecked():
                self.refine.a = value(s['_cell_length_a'])
                self.refine.b = value(s['_cell_length_b'])
                self.refine.c = value(s['_cell_length_c'])
            self.refine.alpha = value(s['_cell_angle_alpha'])
            self.refine.beta = value(s['_cell_angle_beta'])
            self.refine.gamma = value(s['_cell_angle_gamma'])
            if '_space_group_IT_number' in s:
                sgi = sgtbx.space_group_info(s['_space_group_IT_number'])
            elif '_symmetry_Int_Tables_number' in s:
                sgi = sgtbx.space_group_info(s['_symmetry_Int_Tables_number'])
            elif '_space_group_name_H-M_alt' in s:
                sgi = sgtbx.space_group_info(s['_space_group_name_H-M_alt'])
            elif '_symmetry_space_group_name_H-M' in s:
                sgi = sgtbx.space_group_info(
                    s['_symmetry_space_group_name_H-M'])
            elif '_space_group_name_Hall' in s:
                sgi = sgtbx.space_group_info(
                    'hall: '+s['_space_group_name_Hall'])
            elif '_symmetry_space_group_name_Hall' in s:
                sgi = sgtbx.space_group_info(
                    'hall: '+s['_symmetry_space_group_name_Hall'])
            else:
                sgi = None
            if sgi:
                self.refine.space_group = sgi.type().lookup_symbol()
                self.refine.symmetry = sgi.group().crystal_system().lower()
                self.refine.laue_group = sgi.group().laue_group_type()
                self.refine.centring = self.refine.space_group[0]
            self.update_parameters()

    def update_parameters(self):
        self.parameters['space_group'].value = self.refine.space_group
        self.parameters['laue_group'].value = self.refine.laue_group
        self.parameters['symmetry'].value = self.refine.symmetry
        self.parameters['centring'].value = self.refine.centring
        self.parameters['a'].value = self.refine.a
        self.parameters['b'].value = self.refine.b
        self.parameters['c'].value = self.refine.c
        self.parameters['alpha'].value = self.refine.alpha
        self.parameters['beta'].value = self.refine.beta
        self.parameters['gamma'].value = self.refine.gamma

    def set_groups(self):
        if self.space_group:
            try:
                if isinstance(self.space_group, float):
                    sgi = sgtbx.space_group_info(int(self.space_group))
                else:
                    sgi = sgtbx.space_group_info(self.space_group)
            except RuntimeError as error:
                report_error("Defining Lattice", error)
                return
            try:
                self.refine.space_group = sgi.type().lookup_symbol()
                self.refine.symmetry = sgi.group().crystal_system().lower()
                self.refine.laue_group = sgi.group().laue_group_type()
                self.refine.centring = self.refine.space_group[0]
                self.update_parameters()
            except Exception:
                pass

    @property
    def space_group(self):
        return self.parameters['space_group'].value

    @property
    def laue_group(self):
        return self.parameters['laue_group'].value

    def get_symmetry(self):
        return self.parameters['symmetry'].value

    def get_centring(self):
        return self.parameters['centring'].value

    def get_lattice_parameters(self):
        return (self.parameters['a'].value,
                self.parameters['b'].value,
                self.parameters['c'].value,
                self.parameters['alpha'].value,
                self.parameters['beta'].value,
                self.parameters['gamma'].value)

    def set_lattice_parameters(self):
        symmetry = self.get_symmetry()
        if symmetry == 'cubic':
            self.parameters['b'].value = self.parameters['a'].value
            self.parameters['c'].value = self.parameters['a'].value
            self.parameters['alpha'].value = 90.0
            self.parameters['beta'].value = 90.0
            self.parameters['gamma'].value = 90.0
        elif symmetry == 'tetragonal':
            self.parameters['b'].value = self.parameters['a'].value
            self.parameters['alpha'].value = 90.0
            self.parameters['beta'].value = 90.0
            self.parameters['gamma'].value = 90.0
        elif symmetry == 'orthorhombic':
            self.parameters['alpha'].value = 90.0
            self.parameters['beta'].value = 90.0
            self.parameters['gamma'].value = 90.0
        elif symmetry == 'hexagonal':
            self.parameters['b'].value = self.parameters['a'].value
            self.parameters['alpha'].value = 90.0
            self.parameters['beta'].value = 90.0
            self.parameters['gamma'].value = 120.0
        elif symmetry == 'monoclinic':
            self.parameters['alpha'].value = 90.0
            self.parameters['gamma'].value = 90.0

    def get_parameters(self):
        (self.refine.a, self.refine.b, self.refine.c,
         self.refine.alpha, self.refine.beta, self.refine.gamma) = (
            self.get_lattice_parameters())
        self.refine.space_group = self.space_group
        self.refine.laue_group = self.laue_group
        self.refine.symmetry = self.get_symmetry()
        self.refine.centring = self.get_centring()

    def write_parameters(self):
        self.get_parameters()
        self.refine.write_parameters(sample=True)

    def accept(self):
        try:
            self.write_parameters()
            super().accept()
        except NeXusError as error:
            report_error("Defining Lattice", error)
