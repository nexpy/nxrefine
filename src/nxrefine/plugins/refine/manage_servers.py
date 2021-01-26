import os
import subprocess

from nexpy.gui.pyqt import QtWidgets, getOpenFileName

from nexusformat.nexus import *
from nexpy.gui.datadialogs import NXDialog
from nexpy.gui.utils import report_error
from nexpy.gui.widgets import NXPlainTextEdit
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
        if self.server.server_type == 'multinode':
            self.node_editor = NXPlainTextEdit()
            self.node_editor.setPlainText('\n'.join(self.server.read_nodes()))
            self.set_layout(self.labels(('Server Status'), header=True),
                            self.server_layout,
                            self.labels(('List of Nodes'), header=True),
                            self.node_editor,
                            self.close_buttons(save=True))
        else:
            self.set_layout(self.labels(('Server Status'), header=True),
                            self.server_layout,
                            self.close_buttons(save=True))

        self.set_title('Manage Servers')
        self.experiment_directory = None

    def toggle_server(self):
        if self.pushbutton['server'].text() == 'Start Server':
            if self.server.server_type == 'multinode':
                self.read_nodes()
            subprocess.run('nxserver start', shell=True)
        else:
            subprocess.run('nxserver stop', shell=True)
        self.server = NXServer()
        if self.server.is_running():
            self.server_status.setText('Server is running')
            self.pushbutton['server'].setText('Stop Server')
        else:
            self.server_status.setText('Server is not running')
            self.pushbutton['server'].setText('Start Server')

    def read_nodes(self):
        if self.server.server_type == 'multinode':
            nodes = self.node_editor.document().toPlainText().split('\n')
            self.server.write_nodes(nodes)
            self.server.remove_nodes([node for node in self.server.read_nodes()
                                      if node not in nodes])

    def accept(self):
        if self.server.server_type == 'multinode':
            self.read_nodes()
        super(ServerDialog, self).accept()
