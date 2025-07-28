# -----------------------------------------------------------------------------
# Copyright (c) 2022, Argonne National Laboratory.
#
# Distributed under the terms of an Open Source License.
#
# The full license is in the file LICENSE.pdf, distributed with this software.
# -----------------------------------------------------------------------------

import os

from nexpy.gui.dialogs import GridParameters, NXDialog
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

        self.import_button = NXPushButton('Import CIF', self.import_cif)
        self.import_checkbox = NXCheckBox('Update Lattice Parameters')
        self.set_layout(self.root_layout, self.close_buttons(save=True))
        self.set_title('Defining Lattice')

    def choose_entry(self):
        import gemmi.cif
        self.refine = NXRefine(self.root['entry'])
        if self.layout.count() == 2:
            self.parameters = GridParameters()
            self.parameters.add('chemical_formula', self.refine.formula,
                                'Chemical Formula')
            self.parameters.add('space_group', self.refine.space_group,
                                'Space Group', slot=self.set_groups)
            self.parameters.add('laue_group', self.refine.laue_groups,
                                'Laue Group')
            self.parameters.add('symmetry', self.refine.symmetries, 'Symmetry',
                                slot=self.set_lattice_parameters)
            self.parameters.add('centring', self.refine.centrings,
                                'Cell Centring')
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
            self.insert_layout(1, self.parameters.grid(header=False))
            if gemmi.cif:
                self.insert_layout(2, self.make_layout(self.import_button,
                                                       self.import_checkbox,
                                                       align='center'))
        self.update_parameters()

    def import_cif(self):
        import gemmi
        import gemmi.cif as cif
        filename = getOpenFileName(self, 'Open CIF File')
        if os.path.exists(filename):
            cif_doc = cif.read_file(filename)
            found_block = False
            for cif_block in cif_doc:
                if cif_block.find_pair('_cell_length_a'):
                    found_block = True
                    break

            if not found_block:
                # TODO: Should this use report_error()?
                raise ValueError(f"No valid lattice data found in {filename}")

            def value(text):
                if '(' in text:
                    return float(text[:text.index('(')])
                else:
                    return float(text)

            if self.import_checkbox.isChecked():
                self.refine.a = value(cif_block.find_pair('_cell_length_a')[1])
                self.refine.b = value(cif_block.find_pair('_cell_length_b')[1])
                self.refine.c = value(cif_block.find_pair('_cell_length_c')[1])
            self.refine.alpha = value(cif_block.find_pair('_cell_angle_alpha')[1])
            self.refine.beta = value(cif_block.find_pair('_cell_angle_beta')[1])
            self.refine.gamma = value(cif_block.find_pair('_cell_angle_gamma')[1])
            if (cif_pair := cif_block.find_pair('_space_group_IT_number')):
                self.refine.sgi = gemmi.SpaceGroup(cif_pair[1])
            elif (cif_pair := cif_block.find_pair('_symmetry_Int_Tables_number')):
                self.refine.sgi = gemmi.SpaceGroup(cif_pair[1])
            elif (cif_pair := cif_block.find_pair('_space_group_name_H-M_alt')):
                self.refine.sgi = gemmi.SpaceGroup(cif_pair[1])
            elif (cif_pair := cif_block.find_pair('_symmetry_space_group_name_H-M')):
                self.refine.sgi = gemmi.SpaceGroup(cif_pair[1])
            # NOTE: "Different Hall symbols can be used to encode the same
            # symmetry operations. ... That’s why we compare operations not
            # symbols."
            # From: https://gemmi.readthedocs.io/en/latest/symmetry.html
            elif (cif_pair := cif_block.find_pair('_space_group_name_Hall')):
                self.refine.sgi = gemmi.find_spacegroup_by_ops(gemmi.symops_from_hall(cif_pair[1]))
            elif (cif_pair := cif_block.find_pair('_symmetry_space_group_name_Hall')):
                self.refine.sgi = gemmi.find_spacegroup_by_ops(gemmi.symops_from_hall(cif_pair[1]))
            self.update_parameters()

    def update_parameters(self):
        self.parameters['chemical_formula'].value = self.refine.formula
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
        import gemmi
        if self.space_group:
            try:
                if isinstance(self.space_group, float):
                    sgi = gemmi.SpaceGroup(int(self.space_group))
                else:
                    sgi = gemmi.SpaceGroup(self.space_group)
            except RuntimeError as error:
                report_error("Defining Lattice", error)
                return
            try:
                self.refine.sgi = sgi
                self.update_parameters()
            except Exception:
                pass

    @property
    def chemical_formula(self):
        return self.parameters['chemical_formula'].value

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
        self.refine.formula = self.chemical_formula
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
