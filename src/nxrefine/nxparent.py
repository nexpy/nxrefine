# -----------------------------------------------------------------------------
# Copyright (c) 2026, Argonne National Laboratory.
#
# Distributed under the terms of an Open Source License.
#
# The full license is in the file LICENSE.pdf, distributed with this software.
# -----------------------------------------------------------------------------
from pathlib import Path as Path

from nexusformat.nexus import (NeXusError, NXentry, NXfield, NXparameters,
                               NXprocess, NXroot, NXsample, NXsubentry,
                               nxconsolidate, nxopen)
from nexusformat.nexus.tree import natural_sort, string_dtype


class NXParent:

    def __init__(self, filename, entry=None):
        if isinstance(filename, NXroot):
            self.filename = Path(filename.nxfilename).resolve()
            self.root = filename
        elif filename is not None:
            self.filename = Path(filename).resolve()
            if not self.filename.suffix:
                self.filename = self.filename.with_suffix('.nxs')
            if self.filename.is_file():
                self.root = nxopen(self.filename)
            else:
                self.root = NXroot()
        if not self.filename.stem.endswith('_scans'):
            raise ValueError("Parent file must end with '_scans.nxs'")
        self.name = self.filename.name
        self.entry = entry if entry else '/entry'

    def __repr__(self):
        return f"NXParent('{self.name}')"

    def __contains__(self, scan):
        return scan in self.scans

    @property
    def scan_entry(self):
        if self.entry in self.root:
            return self.root[self.entry]
        else:
            return None

    @scan_entry.setter
    def scan_entry(self, value):
        if 'entry' not in self.root:
            self.root['entry'] = value
        else:
            self.root[self.entry] = value

    @property
    def scan_entries(self):
        return ['/entry'] + [s.nxpath for s in self.root['entry'].NXsubentry]

    @property
    def scan_info(self):
        if 'nxscans' in self.scan_entry:
            return self.scan_entry['nxscans']
        else:
            return None

    @scan_info.setter
    def scan_info(self, value):
        if self.scan_entry:
            self.scan_entry['nxscans'] = value

    @property
    def sample_info(self):
        if self.scan_entry and 'sample' in self.scan_entry:
            return self.scan_entry['sample']
        else:
            return None

    @sample_info.setter
    def sample_info(self, value):
        if self.scan_entry:
            self.scan_entry['sample'] = value

    @property
    def settings(self):
        if self.scan_info and 'settings' in self.scan_info:
            return self.scan_info['settings']
        else:
            return None

    @settings.setter
    def settings(self, value):
        if self.scan_info:
            self.scan_info['settings'] = value

    @property
    def transform(self):
        if self.scan_info and 'transform' in self.scan_info:
            return self.scan_info['transform']
        else:
            return None

    @transform.setter
    def transform(self, value):
        if self.scan_info:
            if 'transform' in self.scan_info:
                del self.scan_info['transform']
            self.scan_info['transform'] = value

    @property
    def sample(self):
        return self.filename.parent.parent.name

    @property
    def label(self):
        return self.filename.parent.name

    @property
    def prefix(self):
        return self.filename.stem.replace('scans', '')

    @property
    def directory(self):
        return self.filename.parent

    @property
    def experiment_directory(self):
        return self.filename.parent.parent.parent

    @property
    def task_directory(self):
        return self.experiment_directory / 'tasks'

    @property
    def scans_defined(self):
        return self.scan_info is not None

    @property
    def _sorted_scans(self):
        if self.scans_defined:
            scans = self.scan_info['scans'].nxvalue
            selected = self.scan_info['selected'].nxvalue
            return sorted(zip(scans, selected),
                          key=lambda x: natural_sort(x[0]))
        return []

    @property
    def scans(self):
        scans = self._sorted_scans
        return [f for f, s in scans] if scans else []
  
    @property
    def selected(self):
        scans = self._sorted_scans
        return [bool(s) for f, s in scans] if scans else []

    def index(self, scan):
        return self.scan_info['scans'].nxvalue.index(scan)

    def scan_file(self, scan):
        p = Path(scan)
        if not p.suffix:
            p = p.with_suffix('.nxs')
        if not p.is_absolute():
            p = self.filename.parent / p
        return p

    def scan_directory(self, scan):
        return scan.replace(self.prefix, "")

    @property
    def scan_files(self):
        return [self.scan_file(f) for f in self.scans]

    @property
    def scan_roots(self):
        return [nxopen(self.scan_file(f)) for f in self.scans]

    @property
    def scan_directories(self):
        return [self.scan_directory(f) for f in self.scans]

    @property
    def selected_scans(self):
        if self.scans and self.selected:
            return [self.scan_file(f) for f, s
                    in zip(self.scans, self.selected) if s]
        else:
            return []

    @property
    def other_scan_files(self):
        return sorted([f for f in self.filename.parent.glob("*.nxs")
                       if f.stem not in self.scans 
                       and not f.stem.endswith('_scans')],
                       key=natural_sort)

    @property
    def scan_path(self):
        """The path to the scan variable within the scan files."""
        if self.settings and 'scan_path' in self.settings:
            return self.settings['scan_path'].nxvalue
        else:
            return f'{self.entry}/sample/temperature'

    @property
    def scan_units(self):
        """The units for the scan variable."""
        if self.settings and 'scan_units' in self.settings:
            return self.settings['scan_units'].nxvalue
        else:
            return 'K'

    @property
    def scan_prefix(self):
        if self.filename.name == self.sample + '_scans.nxs':
            return ''
        else:
            return self.filename.stem.replace(
                self.sample, '').replace('scans', '').strip('_') + '_'

    def get_scan_directory(self, value):
        try:
            value = float(value)
        except (ValueError, TypeError):
            pass
        if isinstance(value, float):
            prefix = 'm' if value < 0 else ''
            value = abs(value)
            if value.is_integer():
                value_str = str(int(value))
            else:
                value_str = str(value).replace('.', 'p')
            units = self.scan_units
        else:
            prefix = ''
            value_str = str(value)
            units = ''
        return f"{self.scan_prefix}{prefix}{value_str}{units}"

    def is_parent(self, scan):
        if self.scan_file(scan).is_file():
            with nxopen(self.scan_file(scan), 'r') as root:
                if ('nxscans' in root[self.entry] and
                        'parent' in root[f'{self.entry}/nxscans']):
                    parent = Path(root[f'{self.entry}/nxscans/parent'].nxvalue)
                return self.filename.parent / parent == self.filename
        else:
            return False

    def has_parent(self, scan):
        if self.scan_file(scan).is_file():
            with nxopen(self.scan_file(scan), 'r') as root:
                return ('nxscans' in root[self.entry] and
                        'parent' in root[f'{self.entry}/nxscans'])
        else:
            return False

    def add_parent(self, scan):
        with nxopen(self.scan_file(scan), 'rw') as root:
            if 'nxscans' not in root[self.entry]:
                root[f'{self.entry}/nxscans'] = NXprocess()
            root[f'{self.entry}/nxscans/parent'] = self.filename.name
            root[f'{self.entry}/nxscans'].set_date()

    def add_scan(self, scan, selected=True):
        
        scan_file = self.scan_file(scan)
        if not scan_file.is_file():
            raise ValueError(f"File '{scan_file}' does not exist.")
        with self.root:
            scan_info = self.root[self.scan_info.nxpath]
            if scan_file.stem not in scan_info['scans']:
                current_count = scan_info['scans'].shape[0]
                scan_info['scans'].resize((current_count + 1,))
                scan_info['scans'][current_count] = scan_file.stem
                scan_info['selected'].resize((current_count + 1,))
                scan_info['selected'][current_count] = selected
        self.add_parent(scan)

    def add_scans(self, selected=True):
        directory = self.filename.parent
        pattern = self.filename.name.replace('_scans.nxs', '_*.nxs')
        for scan_file in directory.glob(pattern):
            if scan_file.name != self.name:
                self.add_scan(scan_file, selected)

    def valid_scans(self, scan_group):
        valid_files = []
        for file_path in self.selected_scans:
            try:
                with nxopen(file_path) as root:
                    data = root[self.entry][scan_group]
                    if data.nxsignal and data.nxsignal.exists():
                        valid_files.append(file_path)
            except (NeXusError, OSError):
                continue
        return valid_files

    def create_scan_entry(self, entry):
        with self.root:
            if entry not in self.root['entry']:
                self.root['entry'][entry] = NXsubentry()
            self.entry = self.root['entry'][entry].nxpath
            if 'nxscans' in self.root['entry']:
                self.scan_info = self.root['entry/nxscans']
                self.scan_info.set_date()
            else:
                self.initialize()

    def create_scan_data(self, data_path):
        """Create consolidated scan data."""
        scan_files = self.valid_scans(data_path)
        if scan_files:
            with self.root:
                if data_path in self.root:
                    del self.root[data_path]
                self.root[data_path] = nxconsolidate(scan_files, data_path,
                                                     scan_path=self.scan_path)

    @property
    def scan_groups(self):
        return ['transform', 'masked_transform',
                'symm_transform', 'symm_masked_transform',
                'pdf', 'masked_pdf',
                'total_pdf', 'total_masked_pdf']

    def update_scan_data(self):
        for group in self.scan_groups:
            data_path = f'{self.entry}/{group}'
            try:
                self.create_scan_data(data_path)
            except NeXusError:
                pass

    def reload(self):
        try:
            from nexpy.gui.utils import get_mainwindow
            filenames = self.scan_files + [self.filename]
            mainwindow = get_mainwindow()
            for node in [mainwindow.tree.node_from_file(f) for f in filenames]:
                if node:
                    mainwindow.tree[node].reload()
        except Exception:
            pass

    def initialize(self):
        with self.root:
            if self.scan_entry is None:
                if self.entry in self.root:
                    self.scan_entry = NXentry()
                else:
                    self.scan_entry = NXsubentry()
            if self.scan_info is None:
                self.scan_info = NXprocess()
            if self.settings is None:
                self.settings = NXparameters()
            if 'scans' not in self.scan_info:
                self.scan_info['scans'] = NXfield([], dtype=string_dtype,
                                                  maxshape=(None,))
                self.scan_info['selected'] = NXfield([], dtype=bool,
                                                     maxshape=(None,))
            if self.sample_info is None:
                self.sample_info = NXsample()
            if 'name' not in self.sample_info:
                self.sample_info['name'] = self.sample
            if 'label' not in self.sample_info:
                self.sample_info['label'] = self.label

