# -----------------------------------------------------------------------------
# Copyright (c) 2026, Argonne National Laboratory.
#
# Distributed under the terms of an Open Source License.
#
# The full license is in the file LICENSE.pdf, distributed with this software.
# -----------------------------------------------------------------------------

from pathlib import Path

from nexpy.gui.dialogs import GridParameters, NXDialog
from nexpy.gui.utils import confirm_action, display_message, report_error
from nexusformat.nexus import NeXusError, NXentry, nxopen

from nxrefine.nxparent import NXParent
from nxrefine.nxsettings import NXSettings


def show_dialog():
    try:
        dialog = ParentDialog()
        dialog.show()
    except NeXusError as error:
        report_error("Creating New Parent", error)


class ParentDialog(NXDialog):

    def __init__(self, parent=None):
        super().__init__(parent)

        self.set_layout(self.directorybox('Choose Experiment Directory'), 
                        self.close_layout(save=True))
        self.set_title('New Parent')
        settings = NXSettings().settings
        self.analysis_path = settings['instrument']['analysis_path']

    def choose_directory(self):
        super().choose_directory()
        if not self.task_directory.is_dir():
            display_message("Invalid Directory",
                f"'{self.experiment_directory}' is not a valid directory.")
            self.directoryname.setText('')
            return
        self.settings = NXSettings(self.task_directory).settings
        self.mainwindow.default_directory = str(self.experiment_directory)
        self.sample_box = self.select_box(self.get_samples())
        self.sample_layout = self.make_layout(
            self.action_buttons(('Choose Sample', self.choose_sample)),
            self.sample_box)
        if self.layout.count() == 2:
            self.insert_layout(1, self.sample_layout)
        self.activate()

    def get_samples(self):
        if self.experiment_directory.exists():
            sample_directories = [f for 
                                  f in self.experiment_directory.iterdir()
                                  if f.is_dir()]
        else:
            return []
        samples = []
        for sample_directory in sample_directories:
            label_directories = [f for f in sample_directory.iterdir()
                                 if f.is_dir()]
            for label_directory in label_directories:
                samples.append(
                    label_directory.relative_to(self.experiment_directory))
        return sorted([str(sample) for sample in samples])

    def choose_sample(self):
        if self.layout.count() == 3:
            configurations = self.get_configurations()
            if configurations:
                self.configuration_box = self.select_box(configurations)
                self.configuration_layout = self.make_layout(
                    self.action_buttons(('Choose Experiment Configuration',
                                         self.choose_configuration)),
                    self.configuration_box)
                self.nexus_file = None
                self.insert_layout(2, self.configuration_layout)
            else:
                self.insert_layout(2, self.filebox('Choose Nexus File'))
                self.status_message.setText(
                    'No Configurations Found. Copy from a NeXus file.')
        elif self.layout.count() == 5:
            self.parameters['parent'].value = self.sample

    def get_configurations(self):
        directory = self.experiment_directory / 'configurations'
        if directory.exists():
            return sorted([str(f.name) for f in directory.glob('*.nxs')])
        else:
            return []

    def initialize_parameters(self, default=None):
        fallback = NXSettings(self.task_directory).settings['nxreduce']
        if default is None:
            default = fallback
        else:
            default = {default[field].nxname: default[field].nxvalue
                       for field in default}
        param_map = {
            'threshold':     ('Peak Threshold', fallback['threshold']),
            'first_frame':   ('First Frame', fallback['first_frame']),
            'last_frame':    ('Last Frame', fallback['last_frame']),
            'polar_max':     ('Max. Polar Angle', fallback['polar_max']),
            'hkl_tolerance': ('HKL Tolerance (Å-1)',
                              fallback['hkl_tolerance']),
            'monitor':       ('Normalization Monitor', fallback['monitor']),
            'norm':          ('Normalization Value', fallback['norm']),
            'qmin':          ('Minimum Scattering Q (Å-1)', fallback['qmin']),
            'qmax':          ('Maximum Taper Q (Å-1)', fallback['qmax']),
            'radius':        ('Punch Radius (Å)', fallback['radius']),
            'scan_path':     ('Scan Path', fallback['scan_path']),
            'scan_units':    ('Scan Units', fallback['scan_units'])}

        self.parameters = GridParameters()
        self.parameters.add('parent', self.sample, 'Parent Prefix')
        for key, (label, fallback) in param_map.items():
            self.parameters.add(key, default.get(key, fallback), label)

        self.parameters_grid = self.parameters.grid(header=False, width=200)
        self.parameters_grid.setHorizontalSpacing(10)
        self.parameters_layout = self.make_layout(self.parameters_grid)

    def choose_configuration(self):
        if self.layout.count() == 4:
            self.initialize_parameters()
            self.insert_layout(3, self.parameters_layout)
        else:
            self.parameters['parent'].value = self.sample

    def choose_file(self):
        self.set_default_directory(self.sample_directory)
        super().choose_file(filter="Nexus Files (*.nxs)")
        self.nexus_file = self.get_filename()
        if self.nexus_file is None:
            return
        with nxopen(self.nexus_file) as root:
            if 'nxreduce' in root['entry']:
                default = root['entry/nxreduce']
            elif 'nxscans' in root['entry']:
                default = root['entry/nxscans/settings']
            else:
                default = None
        if self.layout.count() == 4:
            self.initialize_parameters(default)
            self.insert_layout(3, self.parameters_layout)
        else:
            self.parameters['parent'].value = self.sample
        self.status_message.setText("Values copied from NeXus file")

    @property
    def experiment_directory(self):
        directory = self.get_directory()
        if self.analysis_path and directory.name != self.analysis_path:
            directory = directory / self.analysis_path
        return directory

    @property
    def task_directory(self):
        return self.experiment_directory / 'tasks'

    @property
    def configuration_file(self):
        configuration = self.configuration_box.currentText()
        return self.experiment_directory / 'configurations' / configuration

    @property
    def sample(self):
        return Path(self.sample_box.currentText()).parent.name

    @property
    def label(self):
        return Path(self.sample_box.currentText()).name

    @property
    def sample_directory(self):
        return self.experiment_directory / self.sample / self.label

    @property
    def parent_file(self):
        parent_name = self.parameters['parent'].value + '_scans.nxs'
        return self.sample_directory.joinpath(parent_name)

    def copy_file(self, config_file):
        self.parent.copy_file(config_file)

    def create_parent(self):
        self.parent = NXParent(self.parent_file)
        with self.parent.root:
            self.parent.initialize()
            if self.nexus_file:
                self.copy_file(self.nexus_file)
            else:
                self.copy_file(self.configuration_file)
            for p in self.parameters:
                self.parent.settings[p] = self.parameters[p].value
        if self.parent.root.nxfile is None:
            self.parent.root.save(self.parent_file, 'w')

    def accept(self):
        if self.parent_file.is_file() and not confirm_action(
                "Overwrite parent file?", 
                f"'{self.parent_file}' already exists."):
            return
        self.create_parent()
        self.treeview.tree.load(self.parent_file, 'rw')
        super().accept()
