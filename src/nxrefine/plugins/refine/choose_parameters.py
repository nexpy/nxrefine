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
        if 'nxreduce' in self.root['entry']:
            threshold = self.root['entry/nxreduce/threshold']
            first = self.root['entry/nxreduce/first_frame']
            last = self.root['entry/nxreduce/last_frame']
            monitor = self.root['entry/nxreduce/monitor']
            norm = self.root['entry/nxreduce/norm']
        else:
            threshold = 1000.0
            first = 25
            last = 3650
            monitor = 'monitor2'
            norm = 30000

        self.parameters = GridParameters()
        self.parameters.add('threshold', threshold, 'Peak Threshold')
        self.parameters.add('first', first, 'First Frame')
        self.parameters.add('last', last, 'Last Frame')
        self.parameters.add('monitor', ['monitor1', 'monitor2'], 
                            'Normalization Monitor')
        self.parameters['monitor'].value = monitor
        self.parameters.add('norm', norm, 'Normalization Value')

        self.set_layout(self.root_layout,
                        self.parameters.grid(),
                        self.close_buttons(save=True))
        self.set_title('Choose Parameters')

    def choose_root(self):
        self.entries = [self.root[entry] 
                        for entry in self.root if entry != 'entry']
        self.read_parameters()

    def read_parameters(self):
        reduce = NXReduce(self.entries[0])
        if reduce.first:
            self.parameters['first'].value = reduce.first
        if reduce.last:
            self.parameters['last'].value = reduce.last
        if reduce.threshold:
            self.parameters['threshold'].value = reduce.threshold
        if reduce.monitor:
            self.parameters['monitor'].value = reduce.monitor
        if reduce.norm:
            self.parameters['norm'].value = reduce.norm

    def write_parameters(self):
        if 'nxreduce' not in self.root['entry']:
            self.root['entry/nxreduce'] = NXparameters()
        self.root['entry/nxreduce/threshold'] = self.threshold
        self.root['entry/nxreduce/first_frame'] = self.first
        self.root['entry/nxreduce/last_frame'] = self.last
        self.root['entry/nxreduce/monitor'] = self.monitor
        self.root['entry/nxreduce/norm'] = self.norm
        for entry in self.entries:
            if 'peaks' in entry:
                if 'threshold' in entry['peaks'].attrs:
                    del entry['peaks'].attrs['threshold']
                if 'first' in entry['peaks'].attrs:
                    del entry['peaks'].attrs['first']
                if 'last' in entry['peaks'].attrs:
                    del entry['peaks'].attrs['last']
                if 'norm' in entry['peaks'].attrs:
                    del entry['peaks'].attrs['norm']

    @property
    def threshold(self):
        return float(self.parameters['threshold'].value)

    @property
    def first(self):
        return int(self.parameters['first'].value)

    @property
    def last(self):
        return int(self.parameters['last'].value)

    @property
    def monitor(self):
        return self.parameters['monitor'].value

    @property
    def norm(self):
        return float(self.parameters['norm'].value)

    def accept(self):
        self.write_parameters()
        super(ParametersDialog, self).accept()
