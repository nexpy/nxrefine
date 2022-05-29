# -----------------------------------------------------------------------------
# Copyright (c) 2015-2022, NeXpy Development Team.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file COPYING, distributed with this software.
# -----------------------------------------------------------------------------
import os
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
        server_actions = self.action_buttons(('server', self.toggle_server))
        self.server_status = self.label(self.server.status())
        if self.server.is_running():
            self.pushbutton['server'].setText('Stop Server')
        else:
            self.pushbutton['server'].setText('Start Server')
        server_layout = self.make_layout(self.server_status, server_actions)
        text_actions = self.action_buttons(
                           ('Server Log', self.show_log),
                           ('Server Queue', self.show_queue),
                           ('Server Processes', self.show_processes),
                           ('Server Nodes', self.show_nodes))
        self.text_box = NXPlainTextEdit(wrap=False)
        self.text_box.setReadOnly(True)
        self.log_combo = self.select_box(['nxserver'] + self.server.cpus,
                                         slot=self.show_log)
        update_actions = self.action_buttons(
                             ('Clear Queue', self.clear_queue),
                             ('Update Nodes', self.update_nodes))
        close_layout = self.make_layout(self.log_combo, 'stretch',
                                        update_actions, 'stretch',
                                        self.close_buttons(close=True),
                                        align='justified')
        self.set_layout(server_layout, text_actions, self.text_box,
                        close_layout)
        for button in ['Server Nodes', 'Server Log', 'Server Queue',
                       'Server Processes']:
            self.pushbutton[button].setCheckable(True)
        if self.server.server_type == 'multicore':
            self.pushbutton['Server Nodes'].setVisible(False)
            self.pushbutton['Update Nodes'].setVisible(False)
        self.set_title('Manage Servers')
        self.setMinimumWidth(800)
        self.experiment_directory = None
        self.current_text = ''
        self.timer = QtCore.QTimer(self)
        self.timer.timeout.connect(self.update_text)
        self.timer.start(5000)
        self.reset_buttons()

    def toggle_server(self):
        if self.pushbutton['server'].text() == 'Start Server':
            subprocess.run('nxserver start', shell=True)
        else:
            if confirm_action('Stop server?'):
                subprocess.run('nxserver stop', shell=True)
        self.server_status.setText(self.server.status())
        if self.server.is_running():
            self.pushbutton['server'].setText('Stop Server')
        else:
            self.pushbutton['server'].setText('Start Server')

    def update_text(self):
        self.server_status.setText(self.server.status())
        if self.server.is_running():
            self.pushbutton['server'].setText('Stop Server')
        else:
            self.pushbutton['server'].setText('Start Server')
        if self.pushbutton['Server Log'].isChecked():
            self.show_log()
        elif self.pushbutton['Server Queue'].isChecked():
            self.show_queue()
        elif self.pushbutton['Server Processes'].isChecked():
            self.show_processes()
        elif self.pushbutton['Server Nodes'].isChecked():
            self.show_nodes()

    def reset_buttons(self):
        for button in ['Server Log', 'Server Queue', 'Server Processes',
                       'Server Nodes']:
            self.pushbutton[button].setChecked(False)
        self.log_combo.setEnabled(False)
        self.pushbutton['Clear Queue'].setEnabled(False)
        self.pushbutton['Update Nodes'].setEnabled(False)
        self.text_box.setReadOnly(True)

    def show_log(self):
        self.reset_buttons()
        self.pushbutton['Server Log'].setChecked(True)
        self.log_combo.setEnabled(True)
        log_file = os.path.join(self.server.directory,
                                f'{self.log_combo.selected}.log')
        if os.path.exists(log_file):
            with open(log_file) as f:
                text = f.read()
        else:
            text = f"'{log_file}' does not exist"
        if text != self.current_text:
            self.text_box.setPlainText(text)
            self.text_box.verticalScrollBar().setValue(
                self.text_box.verticalScrollBar().maximum())
            self.current_text = text

    def show_queue(self):
        self.reset_buttons()
        self.pushbutton['Server Queue'].setChecked(True)
        self.pushbutton['Clear Queue'].setEnabled(True)
        text = '\n'.join(self.server.queued_tasks())
        if text != self.current_text:
            self.text_box.setPlainText(text)
        self.current_text = text

    def show_processes(self):
        self.reset_buttons()
        self.pushbutton['Server Processes'].setChecked(True)
        patterns = ['nxcombine', 'nxcopy', 'nxfind', 'nxlink', 'nxmax',
                    'nxpdf', 'nxprepare', 'nxreduce', 'nxrefine', 'nxsum',
                    'nxtransform']
        if self.server.server_type == 'multicore':
            command = f"ps auxww | grep -e {' -e '.join(patterns)}"
        else:
            command = "pdsh -w {} 'ps -f' | grep -e {}".format(
                ",".join(self.server.cpus), " -e ".join(patterns))
        process = subprocess.run(command, shell=True, stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE)
        if process.returncode == 0:
            lines = [line for line in sorted(
                process.stdout.decode().split('\n')) if line]
            lines = [line[line.index('nx'):]
                     for line in lines if 'grep' not in line]
            text = '\n'.join(set(lines))
        else:
            text = process.stderr.decode()
        if text != self.current_text:
            self.text_box.setPlainText(text)
        self.current_text = text

    def show_nodes(self):
        self.reset_buttons()
        self.text_box.setReadOnly(False)
        self.pushbutton['Server Nodes'].setChecked(True)
        self.pushbutton['Update Nodes'].setEnabled(True)
        text = '\n'.join(self.server.read_nodes())
        if text != self.current_text:
            self.text_box.setPlainText(text)
            self.current_text = text

    def update_nodes(self):
        if self.pushbutton['Server Nodes'].isChecked():
            nodes = self.text_box.document().toPlainText().split('\n')
            self.server.write_nodes(nodes)
            self.server.remove_nodes([node for node in self.server.read_nodes()
                                      if node not in nodes])

    def clear_queue(self):
        if confirm_action('Clear server queue?'):
            self.server.clear()
