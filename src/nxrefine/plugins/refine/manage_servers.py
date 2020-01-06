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

        self.node_editor = self.editor()
        self.node_editor.setPlainText('\n'.join(self.server.nodes))

        self.experiment_choices =  ['New...'] + list(self.server.experiments)
        self.experiment_combo = self.select_box(self.experiment_choices)

        self.set_layout(self.server_layout,
                        self.labels(('List of Nodes'), header=True),
                        self.node_editor,
                        self.experiment_combo,
                        self.action_buttons(('register', self.register),
                                            ('remove', self.remove)),
                        self.close_buttons(close=True))
        self.node_editor.setFocus()
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

    @property
    def experiment(self):
        return self.experiment_combo.currentText()

    def register(self):
        if self.experiment == 'New...':
            experiment = QtWidgets.QFileDialog.getExistingDirectory(self, 
                                                'Choose Experiment Directory')
            if os.path.exists(experiment):
                self.experiment_combo.addItem(experiment)
                self.server.register(experiment)

    def remove(self):
        self.server.stop(experiment=self.experiment)

