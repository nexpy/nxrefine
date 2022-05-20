# -----------------------------------------------------------------------------
# Copyright (c) 2015-2022, NeXpy Development Team.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file COPYING, distributed with this software.
# -----------------------------------------------------------------------------

import subprocess

from nexpy.gui.datadialogs import NXDialog
from nexpy.gui.pyqt import QtCore
from nexpy.gui.utils import confirm_action, report_error
from nexpy.gui.widgets import NXPlainTextEdit
from nexusformat.nexus import NeXusError
from nxrefine.nxserver import NXServer


def show_dialog():
    try:
        dialog = ServerDialog()
        dialog.show()
    except NeXusError as error:
        report_error("Managing Servers", error)


class ServerDialog(NXDialog):

    def __init__(self, parent=None):

        super().__init__(parent)

        self.server = NXServer()
        self.server_actions = self.action_buttons(('server',
                                                   self.toggle_server))
        self.server_status = self.label(self.server.status())
        if self.server.is_running():
            self.pushbutton['server'].setText('Stop Server')
        else:
            self.pushbutton['server'].setText('Start Server')
        self.server_layout = self.make_layout(self.server_status,
                                              self.server_actions)
        if self.server.server_type == 'multinode':
            self.node_editor = NXPlainTextEdit()
            self.node_editor.setPlainText('\n'.join(self.server.read_nodes()))
        self.queue_editor = NXPlainTextEdit(wrap=False)
        self.queue_editor.setReadOnly(True)
        self.log_editor = NXPlainTextEdit(wrap=False)
        self.log_editor.setReadOnly(True)
        if self.server.server_type == 'multinode':
            self.node_editor = NXPlainTextEdit()
            self.node_editor.setPlainText('\n'.join(self.server.read_nodes()))
            self.set_layout(self.labels(('Server Status'), header=True),
                            self.server_layout,
                            self.labels(('List of Nodes'), header=True),
                            self.node_editor,
                            self.labels(('Server Log'), header=True),
                            self.log_editor,
                            self.labels(('Task Queue'), header=True),
                            self.queue_editor,
                            self.action_buttons(
                                ('Update Nodes', self.update_nodes),
                                ('Clear Queue', self.clear_queue)),
                            self.close_buttons(close=True))
        else:
            self.set_layout(self.labels(('Server Status'), header=True),
                            self.server_layout,
                            self.labels(('Server Log'), header=True),
                            self.log_editor,
                            self.labels(('Task Queue'), header=True),
                            self.queue_editor,
                            self.action_buttons(
                                ('Clear Queue', self.clear_queue)),
                            self.close_buttons(close=True))

        self.set_title('Manage Servers')
        self.setMinimumWidth(800)
        self.experiment_directory = None
        self.log_text = ''
        self.timer = QtCore.QTimer(self)
        self.timer.timeout.connect(self.update_queue)
        self.timer.start(5000)

    def toggle_server(self):
        if self.pushbutton['server'].text() == 'Start Server':
            if self.server.server_type == 'multinode':
                self.update_nodes()
            subprocess.run('nxserver start', shell=True)
        else:
            subprocess.run('nxserver stop', shell=True)
        self.server_status.setText(self.server.status())
        if self.server.is_running():
            self.pushbutton['server'].setText('Stop Server')
        else:
            self.pushbutton['server'].setText('Start Server')

    def update_nodes(self):
        if self.server.server_type == 'multinode':
            nodes = self.node_editor.document().toPlainText().split('\n')
            self.server.write_nodes(nodes)
            self.server.remove_nodes([node for node in self.server.read_nodes()
                                      if node not in nodes])

    def update_queue(self):
        with open(self.server.log_file) as f:
            text = f.read()
        if text != self.log_text:
            self.log_editor.setPlainText(text)
            self.log_editor.verticalScrollBar().setValue(
                self.log_editor.verticalScrollBar().maximum())
            self.log_text = text
        self.queue_editor.setPlainText('\n'.join(self.server.queued_tasks()))
        self.server_status.setText(self.server.status())

    def clear_queue(self):
        if confirm_action('Clear server queue?'):
            self.server.clear()

    def accept(self):
        if self.server.server_type == 'multinode':
            self.update_nodes()
        super().accept()
