# -----------------------------------------------------------------------------
# Copyright (c) 2015-2021, NeXpy Development Team.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file COPYING, distributed with this software.
# -----------------------------------------------------------------------------

from pathlib import Path

from nexpy.gui.datadialogs import NXDialog, GridParameters
from nexpy.gui.utils import report_error
from nexusformat.nexus import NeXusError
from nxrefine.nxdatabase import NXDatabase
from nxrefine.nxsettings import NXSettings


def show_dialog():
    try:
        dialog = ExperimentDialog()
        dialog.show()
    except NeXusError as error:
        report_error("Defining New Experiment", error)


class ExperimentDialog(NXDialog):

    def __init__(self, parent=None):
        super().__init__(parent)
        settings = NXSettings().settings
        self.parameters = GridParameters()
        defaults = settings['instrument']
        self.parameters.add('source', defaults['source'], 'Source Name')
        self.parameters.add('instrument', defaults['instrument'], 'Instrument')
        self.parameters.add('raw_home', defaults['raw_home'],
                            'Raw Data Root Directory')
        self.parameters.add('raw_path', defaults['raw_path'],
                            'Raw Data Subdirectory')
        self.parameters.add('analysis_home', defaults['analysis_home'],
                            'Analysis Root Directory')
        self.parameters.add('analysis_path', defaults['analysis_path'],
                            'Analysis Subdirectory')
        self.parameters.add('experiment', '', 'Name of Experiment')
        self.set_layout(self.parameters.grid(header=False, width=200),
                        self.close_layout(save=True))
        self.set_title('New Experiment')

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
            experiment_path.mkdir(parents=True, exist_ok=True)
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
            settings = NXSettings(task_directory)
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
