import os
import subprocess

from nexpy.gui.pyqt import QtWidgets, getOpenFileName

from nexusformat.nexus import *
from nexpy.gui.datadialogs import NXDialog
from nexpy.gui.utils import report_error
from nxrefine.nxserver import NXServer


def show_dialog():
    try:
        dialog = ServerDialog()
        dialog.show()
    except NeXusError as error:
        report_error("Managing Servers", error)


class ServerDialog(NXDialog):

    def __init__(self, parent=None):

        super(ServerDialog, self).__init__(parent)

        self.server = NXServer()
        self.server_actions = self.action_buttons(('server', 
                                                   self.toggle_server))
        if self.server.is_running():
            self.server_status = self.label('Server is running')
            self.pushbutton['server'].setText('Stop Server')
        else:
            self.server_status = self.label('Server is not running')
            self.pushbutton['server'].setText('Start Server')
        self.server_layout = self.make_layout(self.server_status, 
                                              self.server_actions)

        self.set_layout(self.labels(('Server Status'), header=True),
                        self.server_layout,
                        self.close_buttons(save=True))

        self.set_title('Manage Servers')
        self.experiment_directory = None

    def toggle_server(self):
        if self.pushbutton['server'].text() == 'Start Server':
            subprocess.run('nxserver start', shell=True)
            self.server_status.setText('Server is running')
            self.pushbutton['server'].setText('Stop Server')
        else:
            subprocess.run('nxserver stop', shell=True)
            self.server_status.setText('Server is not running')
            self.pushbutton['server'].setText('Start Server')

    def accept(self):
        super(ServerDialog, self).accept()
