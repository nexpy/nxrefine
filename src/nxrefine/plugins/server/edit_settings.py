# -----------------------------------------------------------------------------
# Copyright (c) 2022, Argonne National Laboratory.
#
# Distributed under the terms of an Open Source License.
#
# The full license is in the file LICENSE.pdf, distributed with this software.
# -----------------------------------------------------------------------------

from nexpy.gui.dialogs import GridParameters, NXDialog
from nexpy.gui.utils import display_message, report_error
from nexpy.gui.widgets import NXScrollArea
from nexusformat.nexus import NeXusError

from nxrefine.nxbeamline import get_beamlines
from nxrefine.nxserver import get_servers
from nxrefine.nxsettings import NXSettings


def show_dialog():
    try:
        dialog = ServerSettingsDialog()
        dialog.show()
    except NeXusError as error:
        report_error("Editing Server Settings", error)


class ServerSettingsDialog(NXDialog):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.settings = NXSettings()
        self.server_parameters = GridParameters()
        defaults = self.settings.settings['server']
        for p in defaults:
            self.server_parameters.add(p, defaults[p], p)
        self.server_parameters['type'].box.editingFinished.connect(
            self.check_server)
        self.instrument_parameters = GridParameters()
        defaults = self.settings.settings['instrument']
        for p in defaults:
            self.instrument_parameters.add(p, defaults[p], p)
        self.instrument_parameters['instrument'].box.editingFinished.connect(
            self.check_beamline)
        self.refine_parameters = GridParameters()
        defaults = self.settings.settings['nxrefine']
        for p in defaults:
            self.refine_parameters.add(p, defaults[p], p)
        self.reduce_parameters = GridParameters()
        defaults = self.settings.settings['nxreduce']
        for p in defaults:
            self.reduce_parameters.add(p, defaults[p], p)
        scroll_layout = self.make_layout(
            self.server_parameters.grid(header=False, title='Server'),
            self.instrument_parameters.grid(header=False,
                                            title='Instrument'),
            self.refine_parameters.grid(header=False, title='NXRefine'),
            self.reduce_parameters.grid(header=False, title='NXReduce'),
            vertical=True)
        self.set_layout(NXScrollArea(scroll_layout),
                        self.close_layout(save=True))
        self.setMinimumWidth(350)
        self.set_title('Edit Settings')

    def check_server(self):
        server_types = get_servers()
        if self.server_parameters['type'].value not in server_types:
            display_message("Server Type Not Supported",
                            "Supported servers are: "
                            f"{', '.join(str(i) for i in server_types)}")
            self.server_parameters['type'].value = (
                self.settings['server']['type'])

    def check_beamline(self):
        beamlines = get_beamlines()
        if self.instrument_parameters['instrument'].value not in beamlines:
            display_message("Beamline Not Supported",
                            "Supported beamlines are: "
                            f"{', '.join(str(i) for i in beamlines)}")
            self.instrument_parameters['instrument'].value = (
                self.settings['instrument']['instrument'])

    def accept(self):
        try:
            for p in self.server_parameters:
                self.settings.set('server', p,
                                  self.server_parameters[p].value)
            for p in self.instrument_parameters:
                self.settings.set('instrument', p,
                                  self.instrument_parameters[p].value)
            for p in self.refine_parameters:
                self.settings.set('nxrefine', p,
                                  self.refine_parameters[p].value)
            for p in self.reduce_parameters:
                self.settings.set('nxreduce', p,
                                  self.reduce_parameters[p].value)
            self.settings.save()
            super().accept()
        except Exception as error:
            report_error("Editing Server Settings", error)
