import numpy as np
from nexpy.gui.datadialogs import BaseDialog, GridParameters
from nexpy.gui.plotview import get_plotview, plotview
from nexpy.gui.utils import report_error
from nexusformat.nexus import *
from nxrefine.nxrefine import NXRefine


def show_dialog():
    try:
        dialog = LatticeDialog()
        dialog.show()
    except NeXusError as error:
        report_error("Defining Lattice", error)


class LatticeDialog(BaseDialog):

    def __init__(self, parent=None):
        super(LatticeDialog, self).__init__(parent)

        self.select_entry(self.choose_entry)

        self.refine = NXRefine()

        self.parameters = GridParameters()
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
        action_buttons = self.action_buttons(('Plot', self.plot_lattice),
                                             ('Save', self.write_parameters))
        self.set_layout(self.entry_layout, self.parameters.grid(), 
                        action_buttons, self.close_buttons())
        self.set_title('Defining Lattice')

    def choose_entry(self):
        self.refine = NXRefine(self.entry)
        self.update_parameters()

    def update_parameters(self):
        self.parameters['symmetry'].value = self.refine.symmetry
        self.parameters['centring'].value = self.refine.centring
        self.parameters['a'].value = self.refine.a
        self.parameters['b'].value = self.refine.b
        self.parameters['c'].value = self.refine.c
        self.parameters['alpha'].value = self.refine.alpha
        self.parameters['beta'].value = self.refine.beta
        self.parameters['gamma'].value = self.refine.gamma

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
            self.refine.write_parameters()
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

