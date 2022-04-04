# -----------------------------------------------------------------------------
# Copyright (c) 2013-2022, NeXpy Development Team.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file COPYING, distributed with this software.
# -----------------------------------------------------------------------------

import os
from configparser import ConfigParser

from nexusformat.nexus import NeXusError


class NXSettings(ConfigParser):
    """A ConfigParser subclass that preserves the case of option names"""

    def __init__(self, directory=None):
        super().__init__(allow_no_value=True)
        self.directory = self.get_directory(server_directory=directory)
        self.file = os.path.join(self.directory, 'settings.ini')
        super().read(self.file)
        sections = self.sections()
        if 'setup' not in sections:
            self.add_section('setup')
        if 'nxrefine' not in sections:
            self.add_section('nxrefine')
        if 'nxreduce' not in sections:
            self.add_section('nxreduce')
        self.add_defaults()

    def get_directory(self, server_directory=None):
        self.home_settings = ConfigParser()
        home_directory = os.path.join(os.path.abspath(os.path.expanduser('~')),
                                      '.nxserver')
        if not os.path.exists(home_directory):
            os.mkdir(home_directory)
        self.home_file = os.path.join(home_directory, 'settings.ini')
        self.home_settings.read(self.home_file)
        if 'setup' not in self.home_settings.sections():
            self.home_settings.add_section('setup')
        if server_directory:
            self.home_settings.set('setup', 'directory', server_directory)
            with open(self.home_file, 'w') as f:
                self.home_settings.write(f)
        elif self.home_settings.has_option('setup', 'directory'):
            server_directory = self.home_settings.get('setup', 'directory')
        else:
            raise NeXusError(
                "Please define settings directory - type 'nxsettings -h'")
        if os.path.basename(server_directory) != 'nxserver':
            server_directory = os.path.join(server_directory, 'nxserver')
        if not os.path.exists(server_directory):
            os.mkdir(server_directory)
        return server_directory

    def add_defaults(self):
        if not self.has_option('setup', 'type'):
            self.set('setup', 'type', 'multicore')
        default = {'wavelength': 0.141, 'distance': 650,
                   'phi': -5.0, 'phi_end': 360.0, 'phi_step': 0.1,
                   'chi': -90.0, 'omega': 0.0, 'x': 0.0, 'y': 0.0,
                   'nsteps': 3, 'frame_rate': 10}
        for p in default:
            if not self.has_option('nxrefine', p):
                self.set('nxrefine', p, default[p])
        default = {'threshold': 50000, 'min_pixels': 10,
                   'first': 25, 'last': 3625,
                   'monitor': 'monitor2', 'norm': 30000,
                   'radius': 0.2, 'qmax': 10.0}
        for p in default:
            if not self.has_option('nxreduce', p):
                self.set('nxreduce', p, default[p])
        self.save()

    def input_defaults(self):
        for s in ['NXRefine', 'NXReduce']:
            print(f'\n{s} Parameters\n-------------------')
            s = s.lower()
            for p in self.options(s):
                value = input(f"{p} [{self.get(s, p)}]: ")
                if value:
                    self.set(s, p, value)
        self.save()

    @property
    def settings(self):
        _settings = {}
        _settings['nxrefine'] = {k: v for (k, v) in self.items('nxrefine')}
        _settings['nxreduce'] = {k: v for (k, v) in self.items('nxreduce')}
        return _settings

    def set(self, section, option, value=None):
        if isinstance(value, int) or isinstance(value, float):
            super().set(section, option, f"{value:g}")
        elif value is not None:
            super().set(section, option, str(value))
        else:
            super().set(section, option)

    def save(self):
        with open(self.file, 'w') as f:
            self.write(f)
