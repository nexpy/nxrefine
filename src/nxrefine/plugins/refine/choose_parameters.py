# -----------------------------------------------------------------------------
# Copyright (c) 2015-2021, NeXpy Development Team.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file COPYING, distributed with this software.
# -----------------------------------------------------------------------------

from nexpy.gui.datadialogs import GridParameters, NXDialog
from nexpy.gui.utils import report_error
from nexusformat.nexus import NeXusError, NXparameters
from nxrefine.nxreduce import NXReduce
from nxrefine.nxsettings import NXSettings


def show_dialog():
    try:
        dialog = ParametersDialog()
        dialog.show()
    except NeXusError as error:
        report_error("Choosing Parameters", error)


class ParametersDialog(NXDialog):

    def __init__(self, parent=None):
        super().__init__(parent)

        self.select_root(self.choose_root)

        default = NXSettings().settings['nxreduce']
        self.parameters = GridParameters()
        self.parameters.add('threshold', default['threshold'],
                            'Peak Threshold')
        self.parameters.add('first', default['first'], 'First Frame')
        self.parameters.add('last', default['last'], 'Last Frame')
        self.parameters.add('monitor', ['monitor1', 'monitor2'],
                            'Normalization Monitor')
        self.parameters['monitor'].value = default['monitor']
        self.parameters.add('norm', default['norm'], 'Normalization Value')
        self.parameters.add('radius', default['radius'], 'Punch Radius (Å)')
        self.parameters.add('qmax', default['qmax'], 'Maximum Taper Q (Å-1)')

        self.set_layout(self.root_layout,
                        self.close_buttons(save=True))
        self.set_title('Choose Parameters')

    def choose_root(self):
        self.entries = [self.root[entry]
                        for entry in self.root if entry != 'entry']
        if self.layout.count() == 2:
            self.layout.insertLayout(1, self.parameters.grid(header=False))
        self.read_parameters()

    def read_parameters(self):
        if 'nxreduce' in self.root['entry']:
            reduce = self.root['entry/nxreduce']
            if 'threshold' in reduce:
                self.parameters['threshold'].value = reduce['threshold']
            if 'first_frame' in reduce:
                self.parameters['first'].value = reduce['first_frame']
            if 'last_frame' in reduce:
                self.parameters['last'].value = reduce['last_frame']
            if 'monitor' in reduce:
                self.parameters['monitor'].value = reduce['monitor']
            if 'norm' in reduce:
                self.parameters['norm'].value = reduce['norm']
            if 'radius' in reduce:
                self.parameters['radius'].value = reduce['radius']
            if 'qmax' in reduce:
                self.parameters['qmax'].value = reduce['qmax']
        else:
            try:
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
                if reduce.radius:
                    self.parameters['radius'].value = reduce.radius
                if reduce.qmax:
                    self.parameters['qmax'].value = reduce.qmax
            except Exception:
                pass

    def write_parameters(self):
        if 'nxreduce' not in self.root['entry']:
            self.root['entry/nxreduce'] = NXparameters()
        self.root['entry/nxreduce/threshold'] = self.threshold
        self.root['entry/nxreduce/first_frame'] = self.first
        self.root['entry/nxreduce/last_frame'] = self.last
        self.root['entry/nxreduce/monitor'] = self.monitor
        self.root['entry/nxreduce/norm'] = self.norm
        self.root['entry/nxreduce/radius'] = self.radius
        self.root['entry/nxreduce/qmax'] = self.qmax

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

    @property
    def radius(self):
        return float(self.parameters['radius'].value)

    def accept(self):
        try:
            self.write_parameters()
            super().accept()
        except NeXusError as error:
            report_error(error)
