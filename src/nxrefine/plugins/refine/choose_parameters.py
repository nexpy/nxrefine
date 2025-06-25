# -----------------------------------------------------------------------------
# Copyright (c) 2022, Argonne National Laboratory.
#
# Distributed under the terms of an Open Source License.
#
# The full license is in the file LICENSE.pdf, distributed with this software.
# -----------------------------------------------------------------------------

import numpy as np
from nexpy.gui.dialogs import GridParameters, NXDialog
from nexpy.gui.plotview import NXPlotView
from nexpy.gui.utils import report_error
from nexusformat.nexus import NeXusError, NXdata, NXfield, NXparameters

from nxrefine.nxreduce import NXMultiReduce, NXReduce
from nxrefine.nxsettings import NXSettings
from nxrefine.nxutils import detector_flipped


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
        self.parameters.add('polar_max', default['polar_max'],
                            'Max. Polar Angle')
        self.parameters.add('hkl_tolerance', default['hkl_tolerance'],
                            'HKL Tolerance (Å-1)')
        self.parameters.add('monitor', default['monitor'],
                            'Normalization Monitor')
        self.parameters['monitor'].value = default['monitor']
        self.parameters.add('norm', default['norm'], 'Normalization Value')
        self.parameters.add('qmin', default['qmin'],
                            'Minimum Scattering  Q (Å-1)')
        self.parameters.add('qmax', default['qmax'], 'Maximum Taper Q (Å-1)')
        self.parameters.add('radius', default['radius'], 'Punch Radius (Å)')

        self.set_layout(self.root_layout,
                        self.close_buttons(save=True))
        self.set_title('Choose Parameters')

    def choose_root(self):
        self.entries = [self.root[entry]
                        for entry in self.root if entry[-1].isdigit()]
        self.reduce = NXReduce(self.root[self.entries[0]])
        if self.layout.count() == 2:
            self.layout.insertLayout(1, self.parameters.grid(header=False))
            self.layout.insertLayout(2, self.action_buttons(
                ('Plot Q-Limits', self.plot_Q_limits)))
            self.layout.insertLayout(3, 
                self.checkboxes(('parent', 'Set As Parent', False)))
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
            if 'polar_max' in reduce:
                self.parameters['polar_max'].value = reduce['polar_max']
            if 'hkl_tolerance' in reduce:
                self.parameters['hkl_tolerance'].value = (
                    reduce['hkl_tolerance'])
            if 'monitor' in reduce:
                self.parameters['monitor'].value = reduce['monitor']
            if 'norm' in reduce:
                self.parameters['norm'].value = reduce['norm']
            if 'qmin' in reduce:
                self.parameters['qmin'].value = reduce['qmin']
            if 'qmax' in reduce:
                self.parameters['qmax'].value = reduce['qmax']
            if 'radius' in reduce:
                self.parameters['radius'].value = reduce['radius']
        else:
            try:
                reduce = NXReduce(self.entries[0])
                if reduce.threshold:
                    self.parameters['threshold'].value = reduce.threshold
                if reduce.first:
                    self.parameters['first'].value = reduce.first
                if reduce.last:
                    self.parameters['last'].value = reduce.last
                if reduce.polar_max:
                    self.parameters['polar_max'].value = reduce.polar_max
                if reduce.hkl_tolerance:
                    self.parameters['hkl_tolerance'].value = (
                        reduce.hkl_tolerance)
                if reduce.monitor:
                    self.parameters['monitor'].value = reduce.monitor
                if reduce.norm:
                    self.parameters['norm'].value = reduce.norm
                if reduce.qmin:
                    self.parameters['qmin'].value = reduce.qmin
                if reduce.qmax:
                    self.parameters['qmax'].value = reduce.qmax
                if reduce.radius:
                    self.parameters['radius'].value = reduce.radius
            except Exception:
                pass

    def write_parameters(self):
        if 'nxreduce' not in self.root['entry']:
            self.root['entry/nxreduce'] = NXparameters()
        self.root['entry/nxreduce/threshold'] = self.threshold
        self.root['entry/nxreduce/first_frame'] = self.first
        self.root['entry/nxreduce/last_frame'] = self.last
        self.root['entry/nxreduce/polar_max'] = self.polar_max
        self.root['entry/nxreduce/hkl_tolerance'] = self.hkl_tolerance
        self.root['entry/nxreduce/monitor'] = self.monitor
        self.root['entry/nxreduce/norm'] = self.norm
        self.root['entry/nxreduce/qmin'] = self.qmin
        self.root['entry/nxreduce/qmax'] = self.qmax
        self.root['entry/nxreduce/radius'] = self.radius

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
    def polar_max(self):
        return float(self.parameters['polar_max'].value)

    @property
    def hkl_tolerance(self):
        return float(self.parameters['hkl_tolerance'].value)

    @property
    def monitor(self):
        return self.parameters['monitor'].value

    @property
    def norm(self):
        return float(self.parameters['norm'].value)

    @property
    def qmin(self):
        return float(self.parameters['qmin'].value)

    @property
    def qmax(self):
        return float(self.parameters['qmax'].value)

    @property
    def radius(self):
        return float(self.parameters['radius'].value)

    def make_parent(self):
        from pathlib import Path
        scan_file = Path(self.root.nxfilename)
        sample = scan_file.stem[:scan_file.stem.rindex('_')] 
        directory = str(scan_file.parent.joinpath(
            scan_file.stem.replace(sample+'_', '')))
        reduce = NXMultiReduce(directory, overwrite=True)
        reduce.make_parent()

    @property
    def pv(self):
        if 'Q-Limits' in self.plotviews:
            return self.plotviews['Q-Limits']
        else:
            return NXPlotView('Q-Limits')

    def plot_Q_limits(self):
        self.reduce.qmin = self.qmin
        self.reduce.qmax = self.qmax
        self.pv.plot(NXdata(self.reduce.transmission_coordinates(),
                            (NXfield(np.arange(self.reduce.shape[1]),
                                     name='y'),
                             NXfield(np.arange(self.reduce.shape[2]),
                                     name='x')),
                            title=f'Q-Limits: {self.root.nxname}'))
        self.pv.aspect = 'equal'
        self.pv.ytab.flipped = detector_flipped(self.reduce.entry)

    def accept(self):
        try:
            self.write_parameters()
            if self.checkbox['parent'].isChecked():
                if self.confirm_action(
                    f"Set '{self.root.nxfilename}' as parent", answer='yes'):
                    self.make_parent()
            super().accept()
        except NeXusError as error:
            report_error("Choosing Parameters", error)
