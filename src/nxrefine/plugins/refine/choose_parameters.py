import os
import numpy as np

from nexusformat.nexus import *
from nexpy.gui.pyqt import QtCore, QtWidgets
from nexpy.gui.datadialogs import NXDialog, GridParameters
from nexpy.gui.utils import report_error, natural_sort

from nxrefine.nxreduce import NXReduce


def show_dialog():
    try:
        dialog = ParametersDialog()
        dialog.show()
    except NeXusError as error:
        report_error("Choosing Parameters", error)


class ParametersDialog(NXDialog):

    def __init__(self, parent=None):
        super(ParametersDialog, self).__init__(parent)

        self.select_root(self.choose_root)

        self.parameters = GridParameters()
        self.parameters.add('threshold', '', 'Threshold')
        self.parameters.add('first', 25, 'First Frame')
        self.parameters.add('last', 3625, 'Last Frame')
        self.parameters.add('radius', 200, 'Radius')
        self.parameters.add('width', 3, 'Frame Width')
        self.parameters.add('norm', '', 'Normalization')

        self.set_layout(self.root_layout,
                        self.parameters.grid(),
                        self.close_buttons(save=True))
        self.set_title('Choose Parameters')

    def choose_root(self):
        self.entries = [self.root[entry] 
                        for entry in self.root if entry != 'entry']
        self.update_parameters()

    def update_parameters(self):
        reduce = NXReduce(self.entries[0])
        if reduce.first:
            self.parameters['first'].value = reduce.first
        if reduce.last:
            self.parameters['last'].value = reduce.last
        if reduce.threshold:
            self.parameters['threshold'].value = reduce.threshold
        if reduce.radius:
            self.parameters['radius'].value = reduce.radius
        if reduce.width:
            self.parameters['width'].value = reduce.width        
        if reduce.norm:
            self.parameters['norm'].value = reduce.norm

    def write_parameters(self, entry):
        if 'peaks' not in entry:
            entry['peaks'] = NXreflections()
        if self.first:
            entry['peaks'].attrs['first'] = np.int(self.first)
        elif 'first' in entry['peaks'].attrs:
            del entry['peaks'].attrs['first']
        if self.last:
            entry['peaks'].attrs['last'] = np.int(self.last)
        elif 'last' in entry['peaks'].attrs:
            del entry['peaks'].attrs['last']
        if self.threshold:
            entry['peaks'].attrs['threshold'] = self.threshold
        elif 'threshold' in entry['peaks'].attrs:
            del entry['peaks'].attrs['threshold']
        if self.radius:
            entry['peaks'].attrs['radius'] = np.int(self.radius)
        elif 'radius' in entry['peaks'].attrs:
            del entry['peaks'].attrs['radius']
        if self.width:
            entry['peaks'].attrs['width'] = np.int(self.width)
        elif 'width' in entry['peaks'].attrs:
            del entry['peaks'].attrs['width']
        if self.norm:
            entry['peaks'].attrs['norm'] = self.norm
        elif 'norm' in entry['peaks'].attrs:
            del entry['peaks'].attrs['norm']

    def get_value(self, key):
        value = self.parameters[key].value
        if isinstance(value, float) and value <= 0:
            return None
        elif isinstance(value, str):
            return None
        else:
            return value
    
    @property
    def threshold(self):
        return self.get_value('threshold')

    @property
    def first(self):
        return self.get_value('first')

    @property
    def last(self):
        return self.get_value('last')

    @property
    def radius(self):
        return self.get_value('radius')

    @property
    def width(self):
        return self.get_value('width')

    @property
    def norm(self):
        return self.get_value('norm')

    def accept(self):
        for entry in self.entries:
            self.write_parameters(entry)
        super(ParametersDialog, self).accept()
