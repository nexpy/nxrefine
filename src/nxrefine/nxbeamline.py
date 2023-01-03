# -----------------------------------------------------------------------------
# Copyright (c) 2015-2023, AXMAS Development Team.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file COPYING, distributed with this software.
# -----------------------------------------------------------------------------

from pathlib import Path

import numpy as np
from nexusformat.nexus import (NXattenuator, NXcollection, NXdata, NXfield,
                               NXfilter, NXinstrument, NXmonitor, NXsource)


def get_beamline(beamline, reduce=None):
    if beamline == 'Sector6':
        return Sector6Beamline(reduce)
    elif beamline == 'QM2':
        return QM2Beamline(reduce)


class NXBeamLine:
    """Generic class containing facility-specific information"""

    def __init__(self, reduce=None):
        self.reduce = reduce
        if self.reduce:
            self.directory = Path(self.reduce.directory)
            self.root = self.reduce.root
            self.entry = self.reduce.entry
        self.probe = 'xrays'

    def __repr__(self):
        return f"NXBeamLine('{self.beamline}')"

    def import_data(self):
        pass

    def read_logs(self):
        pass


class Sector6Beamline(NXBeamLine):

    def __init__(self, reduce=None):
        super().__init__(reduce)
        self.beamline = '6-ID-D'
        self.source = 'APS'
        self.source_name = 'Advanced Photon Source'
        self.source_type = 'Synchrotron X-Ray Source'

    def load_data(self):
        if self.reduce.raw_data_exists():
            return True
        else:
            return False

    def read_logs(self):
        """Read metadata from experimental scans."""
        head_file = self.directory / self.entry.nxname+'_head.txt'
        meta_file = self.directory / self.entry.nxname+'_meta.txt'
        if head_file.exists() and meta_file.exists():
            logs = NXcollection()
        else:
            if not head_file.exists():
                self.logger.info(
                    f"'{self.entry.nxname}_head.txt' does not exist")
            if not meta_file.exists():
                self.logger.info(
                    f"'{self.entry.nxname}_meta.txt' does not exist")
            return None
        with open(head_file) as f:
            lines = f.readlines()
        for line in lines:
            key, value = line.split(', ')
            value = value.strip('\n')
            try:
                value = float(value)
            except Exception:
                pass
            logs[key] = value
        meta_input = np.genfromtxt(meta_file, delimiter=',', names=True)
        for i, key in enumerate(meta_input.dtype.names):
            logs[key] = [array[i] for array in meta_input]

        with self.root.nxfile:
            if 'instrument' not in self.entry:
                self.entry['instrument'] = NXinstrument()
            if 'logs' in self.entry['instrument']:
                del self.entry['instrument/logs']
            self.entry['instrument/logs'] = logs
            frame_number = self.entry['data/frame_number']
            frames = frame_number.size
            if 'MCS1' in logs:
                if 'monitor1' in self.entry:
                    del self.entry['monitor1']
                data = logs['MCS1'][:frames]
                # Remove outliers at beginning and end of frames
                data[0] = data[1]
                data[-1] = data[-2]
                self.entry['monitor1'] = NXmonitor(NXfield(data, name='MCS1'),
                                                   frame_number)
                if 'data/frame_time' in self.entry:
                    self.entry['monitor1/frame_time'] = (
                        self.entry['data/frame_time'])
            if 'MCS2' in logs:
                if 'monitor2' in self.entry:
                    del self.entry['monitor2']
                data = logs['MCS2'][:frames]
                # Remove outliers at beginning and end of frames
                data[0] = data[1]
                data[-1] = data[-2]
                self.entry['monitor2'] = NXmonitor(NXfield(data, name='MCS2'),
                                                   frame_number)
                if 'data/frame_time' in self.entry:
                    self.entry['monitor2/frame_time'] = (
                        self.entry['data/frame_time'])
            if 'source' not in self.entry['instrument']:
                self.entry['instrument/source'] = NXsource()
            self.entry['instrument/source/name'] = self.source
            self.entry['instrument/source/type'] = self.source_type
            self.entry['instrument/source/probe'] = 'x-ray'
            if 'Storage_Ring_Current' in logs:
                self.entry['instrument/source/current'] = (
                    logs['Storage_Ring_Current'])
            if 'SCU_Current' in logs:
                self.entry['instrument/source/undulator_current'] = (
                    logs['SCU_Current'])
            if 'UndulatorA_gap' in logs:
                self.entry['instrument/source/undulator_gap'] = (
                    logs['UndulatorA_gap'])
            if 'Calculated_filter_transmission' in logs:
                if 'attenuator' not in self.entry['instrument']:
                    self.entry['instrument/attenuator'] = NXattenuator()
                self.entry['instrument/attenuator/attenuator_transmission'] = (
                    logs['Calculated_filter_transmission'])
            if 'Shutter' in logs:
                if 'filter' not in self.entry['instrument']:
                    self.entry['instrument/filter'] = NXfilter()
                transmission = NXfield(1.0 - logs['Shutter'][:frames],
                                       name='transmission')
                frames = NXfield(np.array(range(frames)), name='frame_number')
                if 'transmission' in self.entry['instrument/filter']:
                    del self.entry['instrument/filter/transmission']
                self.entry['instrument/filter/transmission'] = (
                    NXdata(transmission, frames))


class QM2Beamline(NXBeamLine):

    def __init__(self, reduce=None):
        super().__init__(reduce)
        self.beamline = 'QM2'
        self.source = 'CHESS'
        self.source_name = 'Cornell High-Energy Synchrotron'
        parts = self.directory.parts
        cycle_path = Path(parts[-6], parts[-5])
        self.raw_directory = Path('/nfs/chess/id4b/') / cycle_path / 'raw6M'

    def load_data(self):
        if self.reduce.raw_data_exists():
            return True
        scan_number = self.entry['scan_number'].nxvalue
        scan_directory = f"{self.sample}_{scan_number:03d}"
        image_directory = (self.raw_directory / self.sample / self.label /
                           self.scan / scan_directory)
        