# -----------------------------------------------------------------------------
# Copyright (c) 2022-2026, Argonne National Laboratory.
#
# Distributed under the terms of an Open Source License.
#
# The full license is in the file LICENSE.pdf, distributed with this software.
# -----------------------------------------------------------------------------

from nexpy.gui.dialogs import GridParameters, NXDialog
from nexpy.gui.utils import report_error
from nexusformat.nexus import NeXusError

from nxrefine.nxparent import NXParent
from nxrefine.nxreduce import NXMultiReduce, NXReduce
from nxrefine.nxsettings import NXSettings


class ParametersDialog(NXDialog):

    def __init__(self, scans_file, subentry=None):
        super().__init__()
        self.parent = NXParent(scans_file, subentry=subentry)
        self.directory = self.parent.directory
        self.sample = self.parent.sample
        self.entries = [self.parent.root[entry]
                        for entry in self.parent.root if entry[-1].isdigit()]
        self.reduce = NXMultiReduce(entry=self.parent.root)
        default = NXSettings(self.reduce.task_directory).settings['nxreduce']
        self.parameters = GridParameters()
        self.parameters.add('threshold', default['threshold'],
                            'Peak Threshold')
        self.parameters.add('first', default['first_frame'], 'First Frame')
        self.parameters.add('last', default['last_frame'], 'Last Frame')
        self.parameters.add('polar_max', default['polar_max'],
                            'Max. Polar Angle')
        self.parameters.add('hkl_tolerance', default['hkl_tolerance'],
                            'HKL Tolerance (Å-1)')
        self.parameters.add('monitor', default['monitor'],
                            'Normalization Monitor')
        self.parameters['monitor'].value = default['monitor']
        self.parameters.add('norm', default['norm'], 'Normalization Value')
        self.parameters.add('sample_transmission',
                            str(default['sample_transmission']),
                            'Apply Sample Transmission')
        self.parameters.add('qmin', default['qmin'] if default['qmin']
                            is not None else '',
                            'Minimum Scattering  Q (Å-1)')
        self.parameters.add('qmax', default['qmax'] if default['qmax']
                            is not None else '',
                            'Maximum Taper Q (Å-1)')
        self.parameters.add('radius', default['radius'], 'Punch Radius (Å)')
        self.parameters.add('mask_t1', default['mask_t1'],
                            'Mask Threshold 1')
        self.parameters.add('mask_h1', default['mask_h1'],
                            'Mask Horizontal Size 1')
        self.parameters.add('mask_t2', default['mask_t2'],
                            'Mask Threshold 2')
        self.parameters.add('mask_h2', default['mask_h2'],
                            'Mask Horizontal Size 2')
        self.parameters.add('scan_path', default['scan_path'], 'Scan Path')
        self.read_parameters()
        self.set_layout(self.parameters.grid(header=False),
                        self.close_layout(save=True))
        self.set_title('Edit Settings')
        self.setMinimumWidth(450)

    def read_parameters(self):
        reduce = self.parent.settings
        if reduce:
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
            if 'sample_transmission' in reduce:
                self.parameters['sample_transmission'].value = str(
                    reduce['sample_transmission'])
            if 'qmin' in reduce:
                self.parameters['qmin'].value = reduce['qmin']
            if 'qmax' in reduce:
                self.parameters['qmax'].value = reduce['qmax']
            if 'radius' in reduce:
                self.parameters['radius'].value = reduce['radius']
            if 'mask_t1' in reduce:
                self.parameters['mask_t1'].value = reduce['mask_t1']
            if 'mask_h1' in reduce:
                self.parameters['mask_h1'].value = reduce['mask_h1']
            if 'mask_t2' in reduce:
                self.parameters['mask_t2'].value = reduce['mask_t2']
            if 'mask_h2' in reduce:
                self.parameters['mask_h2'].value = reduce['mask_h2']
            if 'scan_path' in reduce:
                self.parameters['scan_path'].value = reduce['scan_path']
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
                self.parameters['sample_transmission'].value = str(
                    reduce.sample_transmission)
                qmin = reduce.get_parameter('qmin')
                if qmin not in (None, ''):
                    self.parameters['qmin'].value = qmin
                qmax = reduce.get_parameter('qmax')
                if qmax not in (None, ''):
                    self.parameters['qmax'].value = qmax
                if reduce.radius:
                    self.parameters['radius'].value = reduce.radius
                mp = reduce.mask_parameters
                self.parameters['mask_t1'].value = mp['mask_t1']
                self.parameters['mask_h1'].value = mp['mask_h1']
                self.parameters['mask_t2'].value = mp['mask_t2']
                self.parameters['mask_h2'].value = mp['mask_h2']
                if reduce.scan_path:
                    self.parameters['scan_path'].value = reduce.scan_path
            except Exception:
                pass

    def write_parameters(self):
        with self.parent.root:
            settings = self.parent.scan_entry['nxscans/settings']
            settings['threshold'] = self.threshold
            settings['first_frame'] = self.first
            settings['last_frame'] = self.last
            settings['polar_max'] = self.polar_max
            settings['hkl_tolerance'] = self.hkl_tolerance
            settings['monitor'] = self.monitor
            settings['norm'] = self.norm
            settings['sample_transmission'] = self.sample_transmission
            if self.qmin is not None:
                settings['qmin'] = self.qmin
            elif 'qmin' in settings:
                del settings['qmin']
            if self.qmax is not None:
                settings['qmax'] = self.qmax
            elif 'qmax' in settings:
                del settings['qmax']
            settings['radius'] = self.radius
            settings['mask_t1'] = self.mask_t1
            settings['mask_h1'] = self.mask_h1
            settings['mask_t2'] = self.mask_t2
            settings['mask_h2'] = self.mask_h2
            settings['scan_path'] = self.scan_path
        self.parent.reload()

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
    def sample_transmission(self):
        value = self.parameters['sample_transmission'].value
        if isinstance(value, str):
            return value.strip().lower() in ('true', '1', 'yes', 'on')
        return bool(value)

    @property
    def qmin(self):
        value = self.parameters['qmin'].value
        if value in (None, '', 'None'):
            return None
        return float(value)

    @property
    def qmax(self):
        value = self.parameters['qmax'].value
        if value in (None, '', 'None'):
            return None
        return float(value)

    @property
    def radius(self):
        return float(self.parameters['radius'].value)

    @property
    def mask_t1(self):
        return float(self.parameters['mask_t1'].value)

    @property
    def mask_h1(self):
        return int(self.parameters['mask_h1'].value)

    @property
    def mask_t2(self):
        return float(self.parameters['mask_t2'].value)

    @property
    def mask_h2(self):
        return int(self.parameters['mask_h2'].value)

    @property
    def scan_path(self):
        return self.parameters['scan_path'].value

    def accept(self):
        try:
            self.write_parameters()
            super().accept()
        except NeXusError as error:
            report_error("Editing Settings", error)
