# -----------------------------------------------------------------------------
# Copyright (c) 2022, Argonne National Laboratory.
#
# Distributed under the terms of an Open Source License.
#
# The full license is in the file LICENSE.pdf, distributed with this software.
# -----------------------------------------------------------------------------

from pathlib import Path

from nexpy.gui.datadialogs import NXDialog, GridParameters
from nexpy.gui.utils import confirm_action, report_error
from nexpy.gui.widgets import NXLabel, NXPushButton
from nexusformat.nexus import NeXusError
from nxrefine.nxdatabase import NXDatabase
from nxrefine.nxsettings import NXSettings


def show_dialog():
    try:
        dialog = NewExperimentDialog()
        dialog.show()
    except NeXusError as error:
        report_error("Defining New Experiment", error)


class NewExperimentDialog(NXDialog):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.directory_button = NXPushButton('Choose Experiment Directory',
                                             self.choose_directory)

        settings = NXSettings().settings
        raw_home = settings['instrument']['raw_home']
        analysis_home = settings['instrument']['analysis_home']
        self.parameters = GridParameters()
        defaults = settings['instrument']
        self.parameters.add('source', defaults['source'], 'Source Name')
        self.parameters.add('instrument', defaults['instrument'], 'Instrument')
        self.parameters.add('raw_home', defaults['raw_home'],
                            'Raw Home Directory')
        self.parameters.add('raw_path', defaults['raw_path'],
                            'Raw Data Subdirectory')
        self.parameters.add('analysis_home', defaults['analysis_home'],
                            'Analysis Home Directory')
        self.parameters.add('analysis_path', defaults['analysis_path'],
                            'Analysis Subdirectory')
        self.parameters.add('experiment', '', 'Name of Experiment')
        self.directoryname = NXLabel(settings['instrument']['raw_home'])
        if raw_home and Path(raw_home).exists():
            self.set_default_directory(raw_home)
        else:
            self.set_default_directory(analysis_home)
        self.set_layout(self.make_layout(self.directory_button),
                        self.close_layout(save=True))
        self.set_title('New Experiment')

    def choose_directory(self):
        super().choose_directory()
        directory = self.get_directory()
        if directory:
            directory = Path(directory)
        else:
            self.reject()
            return
        if self.parameters['analysis_home'].value == '':
            ahp = directory.parent
        else:
            ahp = Path(self.parameters['analysis_home'].value).resolve()
            if not ahp.exists():
                self.display_message(
                    'Warning: Analysis Home Error',
                    f"The chosen analysis path {ahp} does not exist")
                return
        if self.parameters['raw_home'].value == '':
            rhp = directory.parent
        else:
            rhp = Path(self.parameters['raw_home'].value).resolve()
            if not rhp.exists():
                self.display_message(
                    'Warning: Raw Home Error',
                    f"The chosen raw path {rhp} does not exist")
                return
        if rhp in directory.parents:
            if directory == rhp:
                directory = directory.parent
            ahp = ahp / directory.parent.relative_to(rhp)
            rhp = rhp / directory.parent.relative_to(rhp)
        elif ahp in directory.parents:
            if directory == ahp:
                directory = directory.parent
            rhp = rhp / directory.parent.relative_to(ahp)
            ahp = ahp / directory.parent.relative_to(ahp)
        else:
            self.display_message(
                'Warning: Raw Home Inconsistency',
                'The chosen experiment directory is not in the default '
                f"location '{rhp}'")
            return
        self.parameters['experiment'].value = str(directory.name)
        self.parameters['raw_home'].value = str(rhp)
        self.parameters['analysis_home'].value = str(ahp)
        self.insert_layout(1, self.parameters.grid(header=False, width=200))
        self.activate()

    def activate(self):
        self.raise_()
        self.activateWindow()
        self.setFocus()

    def accept(self):
        try:
            source = self.parameters['source'].value
            instrument = self.parameters['instrument'].value
            raw_home = self.parameters['raw_home'].value
            raw_path = self.parameters['raw_path'].value
            analysis_home = self.parameters['analysis_home'].value
            analysis_path = self.parameters['analysis_path'].value
            experiment = self.parameters['experiment'].value
            if not Path(raw_home).exists():
                raise NeXusError(f"'{raw_home}' does not exist")
            if not analysis_home:
                analysis_home = raw_home
            elif not Path(analysis_home).exists():
                raise NeXusError(f"'{analysis_home}' does not exist")
            experiment_path = Path(analysis_home) / experiment
            if analysis_path:
                experiment_path = experiment_path / analysis_path
            if not experiment_path.exists():
                if confirm_action("Create experiment directory?",
                                  f"{experiment_path}"):
                    experiment_path.mkdir(parents=True, exist_ok=True)
                else:
                    return
            self.mainwindow.default_directory = str(experiment_path)
            configuration_directory = experiment_path / 'configurations'
            configuration_directory.mkdir(exist_ok=True)
            task_directory = experiment_path / 'tasks'
            task_directory.mkdir(exist_ok=True)
            _ = NXDatabase(task_directory / 'nxdatabase.db')
            calibration_directory = experiment_path / 'calibrations'
            calibration_directory.mkdir(exist_ok=True)
            script_directory = experiment_path / 'scripts'
            script_directory.mkdir(exist_ok=True)
            settings = NXSettings(directory=task_directory, create=True)
            settings.set('instrument', 'source', source)
            settings.set('instrument', 'instrument', instrument)
            settings.set('instrument', 'raw_home', raw_home)
            settings.set('instrument', 'raw_path', raw_path)
            settings.set('instrument', 'analysis_home', analysis_home)
            settings.set('instrument', 'analysis_path', analysis_path)
            settings.set('instrument', 'experiment', experiment)
            settings.save()
            super().accept()
        except Exception as error:
            report_error("Defining New Experiment", error)
