import os
import subprocess

from nexusformat.nexus import *
from nexpy.gui.datadialogs import BaseDialog
from nexpy.gui.utils import report_error
from nxrefine.nxserver import NXServer


def show_dialog():
    try:
        dialog = ServerDialog()
        dialog.show()
    except NeXusError as error:
        report_error("Managing Servers", error)


class ServerDialog(BaseDialog):

    def __init__(self, parent=None):
        super(ServerDialog, self).__init__(parent)

        self.node_editor = self.editor()
        self.set_layout(self.directorybox('Choose Experiment Directory',
                                          slot=self.choose_directory,
                                          default=False),
                        self.action_buttons(('server', self.toggle_server)),
                        self.labels(('List of Nodes'), header=True),
                        self.node_editor,
                        self.close_buttons(close=True))
        self.pushbutton['server'].setText('Start/Stop Server')
        self.node_editor.setFocus()
        self.set_title('Manage Servers')
        self.experiment_directory = None

    def choose_directory(self):
        super(ServerDialog, self).choose_directory()
        self.experiment_directory = self.get_directory()
        self.mainwindow.default_directory = self.experiment_directory
        self.server = NXServer(self.experiment_directory)
        self.node_editor.setPlainText('\n'.join(self.server.nodes))
        if self.server.is_running():
            self.pushbutton['server'].setText('Stop Server')
        else:
            self.pushbutton['server'].setText('Start Server')

    def toggle_server(self):
        switches = '-c %s -g %s' % (os.path.dirname(self.experiment_directory),
                                    os.path.basename(self.experiment_directory))
        if not self.experiment_directory:
            raise NeXusError('Experiment directory not chosen')
        elif self.pushbutton['server'].text() == 'Start Server':
            subprocess.run('nxserver %s start' % switches, shell=True)
            self.pushbutton['server'].setText('Stop Server')
        else:
            subprocess.run('nxserver %s stop' % switches, shell=True)
            self.pushbutton['server'].setText('Start Server')
