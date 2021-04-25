import os

import numpy as np
try:
    from cctbx import sgtbx
    import iotbx.cif as cif
except ImportError:
    sgtbx = None

from nexpy.gui.datadialogs import NXDialog, GridParameters
from nexpy.gui.plotview import get_plotview, plotview
from nexpy.gui.pyqt import getOpenFileName
from nexpy.gui.utils import report_error
from nexpy.gui.widgets import NXCheckBox, NXPushButton
from nexusformat.nexus import *
from nxrefine.nxrefine import NXRefine


def show_dialog():
    try:
        dialog = LatticeDialog()
        dialog.show()
    except NeXusError as error:
        report_error("Defining Lattice", error)


class LatticeDialog(NXDialog):

    def __init__(self, parent=None):
        super(LatticeDialog, self).__init__(parent)

        self.select_root(self.choose_entry)

        self.refine = NXRefine()

        self.parameters = GridParameters()
        self.parameters.add('space_group', self.refine.space_group, 
                            'Space Group', slot=self.set_groups)
        self.parameters.add('laue_group', self.refine.laue_group, 
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
        self.parameters.add('alpha', self.refine.alpha, 'Unit Cell - alpha (deg)', 
                            slot=self.set_lattice_parameters)
        self.parameters.add('beta', self.refine.beta, 'Unit Cell - beta (deg)',
                            slot=self.set_lattice_parameters)
        self.parameters.add('gamma', self.refine.gamma, 'Unit Cell - gamma (deg)', 
                            slot=self.set_lattice_parameters)
        self.parameters['symmetry'].value = self.refine.symmetry
        self.parameters['centring'].value = self.refine.centring
        self.import_button = NXPushButton('Import CIF', self.import_cif)
        self.import_checkbox = NXCheckBox('Update Lattice Parameters')
        if sgtbx is None:
            self.import_button.setVisible(False)
            self.import_checkbox.setVisible(False)
        self.set_layout(self.root_layout, self.parameters.grid(), 
                        self.action_buttons(('Plot', self.plot_lattice),
                                            ('Save', self.write_parameters)),
                        self.make_layout(self.import_button, 
                                         self.import_checkbox, align='center'),
                        self.close_buttons())
        self.set_title('Defining Lattice')

    def choose_entry(self):
        self.refine = NXRefine(self.root['entry'])
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
                sgi = sgtbx.space_group_info(s['_symmetry_space_group_name_H-M'])
            elif '_space_group_name_Hall' in s:
                sgi = sgtbx.space_group_info('hall: '+s['_space_group_name_Hall'])
            elif '_symmetry_space_group_name_Hall' in s:
                sgi = sgtbx.space_group_info('hall: '+s['_symmetry_space_group_name_Hall'])
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

    def plot_lattice(self):
        try:
            self.get_parameters()
            self.plot_peaks(self.refine.xp, self.refine.yp)
            polar_min, polar_max = plotview.xaxis.get_limits()
            self.plot_rings(polar_max)
        except NeXusError as error:
            report_error('Plotting Lattice', error)

    def write_parameters(self):
        try:
            self.get_parameters()
            self.refine.write_parameters(sample=True)
        except NeXusError as error:
            report_error('Defining Lattice', error)

    def plot_peaks(self, x, y):
        try:
            polar_angles, azimuthal_angles = self.refine.calculate_angles(x, y)
            if polar_angles[0] > polar_angles[-1]:
                polar_angles = polar_angles[::-1]
                azimuthal_angles = azimuthal_angles[::-1]
            azimuthal_field = NXfield(azimuthal_angles, name='azimuthal_angle')
            azimuthal_field.long_name = 'Azimuthal Angle'
            polar_field = NXfield(polar_angles, name='polar_angle')
            polar_field.long_name = 'Polar Angle'
            plotview = get_plotview()
            plotview.plot(NXdata(azimuthal_field, polar_field, title='Peak Angles'))
        except NeXusError as error:
            report_error('Plotting Lattice', error)

    def plot_rings(self, polar_max=None):
        if polar_max is None:
            polar_max = self.refine.polar_max
        peaks = self.refine.calculate_rings(polar_max)
        plotview = get_plotview()
        plotview.vlines(peaks, colors='r', linestyles='dotted')
        plotview.draw()

