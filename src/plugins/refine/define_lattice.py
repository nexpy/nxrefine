import numpy as np
from nexpy.gui.datadialogs import BaseDialog, GridParameters
from nexpy.gui.mainwindow import report_error
from nexpy.gui.plotview import plotview
from nexusformat.nexus import NeXusError
from nxpeaks.nxrefine import NXRefine


def show_dialog(parent=None):
    try:
        dialog = LatticeDialog(parent)
        dialog.show()
    except NeXusError as error:
        report_error("Defining Lattice", error)
        

class LatticeDialog(BaseDialog):

    def __init__(self, parent=None):
        super(LatticeDialog, self).__init__(parent)

        self.select_entry(self.choose_entry)

        self.refine = NXRefine(self.entry)
        self.refine.read_parameters()

        self.parameters = GridParameters()
        self.parameters.add('centring', self.refine.centrings, 'Cell Centring')
        self.parameters['centring'].value = self.refine.centring
        self.parameters.add('a', self.refine.a, 'Unit Cell - a (Ang)')
        self.parameters.add('b', self.refine.b, 'Unit Cell - b (Ang)')
        self.parameters.add('c', self.refine.c, 'Unit Cell - c (Ang)')
        self.parameters.add('alpha', self.refine.alpha, 'Unit Cell - alpha (deg)')
        self.parameters.add('beta', self.refine.beta, 'Unit Cell - beta (deg)')
        self.parameters.add('gamma', self.refine.gamma, 'Unit Cell - gamma (deg)')
        action_buttons = self.action_buttons(('Plot', self.plot_peaks),
                                             ('Save', self.write_parameters))
        self.set_layout(self.entry_layout, self.parameters.grid(), 
                        action_buttons, self.close_buttons())
        self.set_title('Defining Lattice')

    def choose_entry(self):
        self.refine = NXRefine(self.entry)
        self.update_parameters()

    def update_parameters(self):
        self.parameters['centring'].value = self.refine.centring
        self.parameters['a'].value = self.refine.a
        self.parameters['b'].value = self.refine.b
        self.parameters['c'].value = self.refine.c
        self.parameters['alpha'].value = self.refine.alpha
        self.parameters['beta'].value = self.refine.beta
        self.parameters['gamma'].value = self.refine.gamma

    def get_centring(self):
        return self.parameters['centring'].value

    def get_lattice_parameters(self):
        return (self.parameters['a'].value,
                self.parameters['b'].value,
                self.parameters['c'].value,
                self.parameters['alpha'].value,
                self.parameters['beta'].value,
                self.parameters['gamma'].value)

    def get_parameters(self):
        self.refine.a, self.refine.b, self.refine.c, \
            self.refine.alpha, self.refine.beta, self.refine.gamma = self.get_lattice_parameters()
        self.refine.centring = self.get_centring()

    def plot_peaks(self):
        try:
            self.get_parameters()
            self.refine.plot_peaks(self.refine.xp, self.refine.yp)
            polar_min, polar_max = plotview.xaxis.get_limits()
            self.refine.plot_rings(polar_max)
        except NeXusError as error:
            report_error('Plotting Lattice', error)

    def write_parameters(self):
        try:
            self.get_parameters()
            self.refine.write_parameters()
        except NeXusError as error:
            report_error('Defining Lattice', error)
