# -----------------------------------------------------------------------------
# Copyright (c) 2026, Argonne National Laboratory.
#
# Distributed under the terms of an Open Source License.
#
# The full license is in the file LICENSE.pdf, distributed with this software.
# -----------------------------------------------------------------------------
import datetime
import logging
import shutil
from pathlib import Path as Path

from nexusformat.nexus import (NeXusError, NXcollection, NXdata, NXentry,
                               NXfield, NXgroup, NXnote, NXparameters,
                               NXprocess, NXroot, NXsample, NXsubentry,
                               nxconsolidate, nxopen)
from nexusformat.nexus.tree import natural_sort, string_dtype


class NXParent:

    def __init__(self, filename, subentry=None):
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
        if isinstance(subentry, NXsubentry):
            self._subentry = subentry.nxname
        else:
            self._subentry = subentry or ''

    @property
    def subentry_name(self):
        """String name of the current subentry within '/entry', or ''."""
        return self._subentry

    @property
    def subentry(self):
        """The NXsubentry group within '/entry', or None."""
        if (self._subentry and self.entry is not None
                and self._subentry in self.entry):
            return self.entry[self._subentry]
        return None

    @property
    def entry_path(self):
        """String path to the active entry: '/entry' or '/entry/{subentry}'."""
        return f'/entry/{self._subentry}' if self._subentry else '/entry'

    @property
    def entry(self):
        """NXentry group at '/entry' in the scans file."""
        if 'entry' in self.root:
            return self.root['entry']
        return None

    @entry.setter
    def entry(self, value):
        parts = str(value).strip('/').split('/')
        self._subentry = parts[-1] if len(parts) > 1 else ''

    def __repr__(self):
        return f"NXParent('{self.name}')"

    def __contains__(self, scan):
        return scan in self.scans

    @property
    def scan_entry(self):
        """NXentry or NXsubentry currently being worked on."""
        if self._subentry:
            return self.subentry
        return self.entry

    @scan_entry.setter
    def scan_entry(self, value):
        if 'entry' not in self.root:
            self.root['entry'] = value
        elif self._subentry:
            self.entry[self._subentry] = value
        else:
            self.root['entry'] = value

    @property
    def scan_entries(self):
        return ['/entry'] + [s.nxpath for s in self.root['entry'].NXsubentry]

    @property
    def scan_subentries(self):
        return [s.nxname for s in self.root['entry'].NXsubentry]

    @property
    def scan_info(self):
        if self.scan_entry and 'nxscans' in self.scan_entry:
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

    def get_setting(self, name, default=None):
        """Return a single setting from /entry/nxscans/settings."""
        if self.settings is not None and name in self.settings:
            return self.settings[name].nxvalue
        return default

    def write_settings(self, **kwargs):
        """Write reduction settings to /entry/nxscans/settings."""
        with nxopen(self.filename, 'rw') as root:
            entry = root[self.entry_path]
            if 'nxscans' not in entry:
                entry['nxscans'] = NXprocess()
            if 'settings' not in entry['nxscans']:
                entry['nxscans']['settings'] = NXparameters()
            settings = entry['nxscans']['settings']
            for name, value in kwargs.items():
                if value is not None:
                    settings[name] = value

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
            if isinstance(scans, str):
                scans = [scans]
            if not hasattr(selected, '__iter__'):
                selected = [selected]
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
            return f'{self.entry_path}/sample/temperature'

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
        if isinstance(scan, NXroot):
            scan = scan.nxfilename
        if self.scan_file(scan).is_file():
            with nxopen(self.scan_file(scan), 'r') as root:
                if f'{self.entry_path}/nxscans/parent' in root:
                    parent = Path(
                        root[f'{self.entry_path}/nxscans/parent'].nxvalue)
                    return self.filename.parent / parent == self.filename
                return False
        else:
            return False

    def has_parent(self, scan):
        if isinstance(scan, NXroot):
            scan = scan.nxfilename
        if self.scan_file(scan).is_file():
            with nxopen(self.scan_file(scan), 'r') as root:
                return f'{self.entry_path}/nxscans/parent' in root
        else:
            return False

    def add_parent(self, scan):
        with nxopen(self.scan_file(scan), 'rw') as root:
            if self._subentry and self._subentry not in root['entry']:
                root['entry'][self._subentry] = NXsubentry()
            if 'nxscans' not in root[self.entry_path]:
                root[f'{self.entry_path}/nxscans'] = NXprocess()
            root[f'{self.entry_path}/nxscans/parent'] = self.filename.name
            root[f'{self.entry_path}/nxscans'].set_date()

    def backup_scan(self, scan):
        """Copy scan file to {base_dir}/backup/ before restructuring."""
        src = self.scan_file(scan)
        backup_dir = src.parent / 'backup'
        backup_dir.mkdir(exist_ok=True)
        ts = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        dst = backup_dir / f'{src.stem}_{ts}.nxs'
        shutil.copy2(src, dst)
        return dst

    def clean_backups(self, days=30):
        """Delete backup files in {base_dir}/backup/ older than `days` days."""
        backup_dir = self.filename.parent / 'backup'
        if not backup_dir.exists():
            return
        cutoff = datetime.datetime.now() - datetime.timedelta(days=days)
        for path in backup_dir.glob('*.nxs'):
            if datetime.datetime.fromtimestamp(path.stat().st_mtime) < cutoff:
                path.unlink()

    def restore_scan(self, scan):
        """Restore the most recent backup of a scan file."""
        dst = self.scan_file(scan)
        backup_dir = dst.parent / 'backup'
        if not backup_dir.exists():
            raise FileNotFoundError(
                f"No backup directory found at '{backup_dir}'")
        backups = sorted(backup_dir.glob(f'{dst.stem}_*.nxs'))
        if not backups:
            raise FileNotFoundError(f"No backups found for '{dst.stem}'")
        shutil.copy(backups[-1], dst)
        return backups[-1]

    def _needs_restructuring(self, root):
        """Return True if the scan file has legacy structure to migrate."""
        for name, group in root.entries.items():
            if not isinstance(group, NXentry):
                continue
            if (name == 'entry' and 'nxreduce' in group
                    and 'deprecated' not in group['nxreduce'].attrs):
                return True
            targets = [group] + [sub for sub in group.entries.values()
                                  if isinstance(sub, NXsubentry)]
            for target in targets:
                if 'nxworkflow' in target:
                    continue
                if any(isinstance(item, NXprocess) and 'program' in item
                       for item in target.entries.values()):
                    return True
        return False

    def restructure_scan(self, scan):
        """Migrate legacy NXprocess groups into nxworkflow."""
        deprecation_msg = (
            "Reduction settings are now read from and written to "
            "the parent file's /entry/nxscans/settings; this group "
            "is retained for backward compatibility but is no "
            "longer consulted.")
        with nxopen(self.scan_file(scan), 'rw') as root:
            for name, group in list(root.entries.items()):
                if not isinstance(group, NXentry):
                    continue
                if (name == 'entry' and 'nxreduce' in group
                        and 'deprecated' not in group['nxreduce'].attrs):
                    group['nxreduce'].attrs['deprecated'] = deprecation_msg
                targets = [group] + [sub for sub in group.entries.values()
                                     if isinstance(sub, NXsubentry)]
                for target in targets:
                    if 'nxworkflow' in target:
                        continue
                    legacy = [n for n, item in target.entries.items()
                              if isinstance(item, NXprocess) and
                              'program' in item]
                    if legacy:
                        target['nxworkflow'] = NXcollection()
                        for n in legacy:
                            target.move(n, target['nxworkflow'])

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
        with nxopen(scan_file) as root:
            needs = self._needs_restructuring(root)
        if needs:
            self.clean_backups()
            self.backup_scan(scan)
            self.restructure_scan(scan)

    def add_scans(self, selected=True):
        directory = self.filename.parent
        pattern = self.filename.name.replace('_scans.nxs', '_*.nxs')
        for scan_file in directory.glob(pattern):
            if scan_file.name != self.name:
                self.add_scan(scan_file, selected)

    def sync_scans(self, selected=True):
        """Register scan files in the directory that name this parent.

        Reconciles a parent copied to another disk before its scans were
        registered: each scan file carries a `/entry/nxscans/parent`
        back-pointer, so the parent's scan list can be rebuilt from them.
        Only files whose back-pointer matches this parent (``is_parent``)
        and that are not already listed are added. Returns the list of
        newly added stems.
        """
        if not self.scans_defined:
            return []
        added = []
        for scan_file in self.other_scan_files:
            if self.is_parent(scan_file):
                self.add_scan(scan_file, selected=selected)
                added.append(scan_file.stem)
        return added

    def valid_scans(self, scan_group):
        valid_files = []
        for file_path in self.selected_scans:
            try:
                with nxopen(file_path) as root:
                    data = root[self.entry_path][scan_group]
                    if data.nxsignal and data.nxsignal.exists():
                        valid_files.append(file_path)
            except (NeXusError, OSError):
                continue
        return valid_files

    def create_scan_entry(self, entry, description=None):
        """Create a new subentry with its own nxscans group.

        Parameters
        ----------
        entry : str
            Name of the new subentry.
        description : str, optional
            Free-text description, stored as ``nxscans/description``
            (NXnote).
        """
        with self.root:
            if entry not in self.root['entry']:
                self.root['entry'][entry] = NXsubentry()
            root_scans = (self.root['entry/nxscans']
                          if 'nxscans' in self.root['entry'] else None)
            self._subentry = entry
            self.initialize()
            if root_scans is not None:
                for field in ('scans', 'selected', 'parent'):
                    if field in root_scans and field not in self.scan_info:
                        self.scan_info[field] = NXfield(
                            root_scans[field].nxvalue,
                            dtype=root_scans[field].dtype,
                            maxshape=root_scans[field].maxshape)
            if description:
                self.scan_info['description'] = NXnote(entry, description)
            if ('sample' in self.root['entry'] and
                    'sample' not in self.root['entry'][entry]):
                self.root['entry'][entry].makelink(
                    self.root['entry/sample'])

    def create_scan_data(self, data_path):
        """Create consolidated scan data.

        Mirrors the NXclass of any intermediate group from the first
        valid scan file so paths like ``entry/frame_sums/summed_data``
        work even when the parent does not yet contain ``frame_sums``.
        Opens a fresh file handle each call so it is safe to call from
        a background thread.
        """
        scan_files = self.valid_scans(data_path)
        if not scan_files:
            return
        scan_data = nxconsolidate(scan_files, data_path,
                                  scan_path=self.scan_path)
        parts = data_path.strip('/').split('/')
        intermediate_types = []
        if len(parts) > 1:
            with nxopen(scan_files[0]) as src:
                src_cursor = src
                for name in parts[:-1]:
                    src_cursor = src_cursor[name]
                    intermediate_types.append((name, type(src_cursor)))
        with nxopen(self.filename, 'rw') as root:
            cursor = root
            for name, cls in intermediate_types:
                if name not in cursor:
                    cursor[name] = cls()
                cursor = cursor[name]
            if data_path in root:
                del root[data_path]
            root[data_path] = scan_data

    def _data_paths(self):
        """Yield NXdata paths at depth 1 and 2 under entry_path in scan files.

        Opens the first selected scan file to discover what groups exist,
        then yields only the paths that correspond to NXdata groups.
        Groups named in _skip and NXentry/NXsubentry children are excluded
        from recursion so that raw data and metadata are not consolidated.
        The scan file is closed before any path is yielded so its lock is
        not held across subsequent consolidation calls.
        """
        if not self.selected_scans:
            return
        _skip = frozenset(
            {'data', 'nxscans', 'nxworkflow', 'nxreduce', 'instrument', 'sample'})
        paths = []
        try:
            with nxopen(self.selected_scans[0]) as scan_root:
                target = scan_root[self.entry_path]
                for name, child in target.entries.items():
                    if name in _skip:
                        continue
                    path1 = f'{self.entry_path}/{name}'
                    if isinstance(child, NXdata):
                        paths.append(path1)
                    elif isinstance(child, NXgroup) and not isinstance(
                            child, (NXentry, NXsubentry)):
                        for name2, grandchild in child.entries.items():
                            if isinstance(grandchild, NXdata):
                                paths.append(f'{path1}/{name2}')
        except (NeXusError, OSError, KeyError):
            return
        yield from paths

    def update_scan_data(self):
        """Consolidate scan data for all discovered NXdata groups."""
        for data_path in self._data_paths():
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
            logging.exception("NXParent.reload failed")

    def reload_parent(self):
        try:
            from nexpy.gui.utils import get_mainwindow
            mainwindow = get_mainwindow()
            node = mainwindow.tree.node_from_file(self.filename)
            if node:
                mainwindow.tree[node].reload()
        except Exception:
            logging.exception("NXParent.reload_parent failed")

    def copy_file(self, config_file):
        with nxopen(config_file) as root:
            for entry in root.entries:
                if entry not in self.root:
                    self.root[entry] = NXentry()
                if 'instrument' in root[entry]:
                    instrument = root[entry]['instrument']
                    if 'instrument' in self.root[entry]:
                        del self.root[entry]['instrument']
                    self.root[entry]['instrument'] = instrument
                if 'data' in root[entry]:
                    data = root[entry]['data']
                    if 'data' in self.root[entry]:
                        del self.root[entry]['data']
                    self.root[entry]['data'] = data
            if 'sample' in root['entry']:
                if 'sample' in self.root['entry']:
                    del self.root['entry/sample']
                self.sample_info = root['entry/sample']
            if 'transform' in root['entry']:
                L, K, H = root['entry/transform'].nxaxes
                self.transform = NXdata(axes=(L, K, H))
        self._link_position_samples()

    def _link_position_samples(self):
        """Link /f{n}/sample to /entry/sample for every per-position entry.

        Idempotent: skips entries that already have a sample group so
        this is safe to call from copy_file, add_scan, or any future
        initialization path.
        """
        if 'entry' not in self.root or 'sample' not in self.root['entry']:
            return
        sample = self.root['entry/sample']
        for name in list(self.root.entries):
            if name == 'entry' or not name[-1].isdigit():
                continue
            entry = self.root[name]
            if 'sample' in entry:
                continue
            entry.makelink(sample)

    def initialize(self):
        with self.root:
            if self.scan_entry is None:
                if self.subentry_name:
                    self.scan_entry = NXsubentry(name=self.subentry_name)
                else:
                    self.scan_entry = NXentry()
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

