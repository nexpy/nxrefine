import os
import subprocess

from nexusformat.nexus import *
from nexpy.gui.datadialogs import BaseDialog
from nexpy.gui.utils import report_error


def show_dialog():
    dialog = ServerDialog()
    dialog.show()
#    except NeXusError as error:
#        report_error("Defining New Experiment", error)


class ServerDialog(BaseDialog):

    def __init__(self, parent=None):
        super(ServerDialog, self).__init__(parent)

        self.node_editor = self.editor()
        self.set_layout(self.directorybox('Choose Experiment Directory',
                                          slot=self.choose_directory),
                        self.checkboxes(('server', 'Server', False),
                                        ('watcher', 'Watcher', False),
                                        ('logger', 'Logger', False)),
                        self.labels(('Nodes')),
                        self.node_editor,
                        self.close_buttons())
        self.node_editor.setFocus()
        self.set_title('Manage Servers')
        self.home_directory = None

    def choose_directory(self):
        super(ServerDialog, self).choose_directory()
        self.home_directory = self.get_directory()
        self.mainwindow.default_directory = self.home_directory
        task_directory = os.path.join(self.home_directory, 'tasks')
        if not os.path.exists(task_directory):
            os.makedirs(task_directory)
        if os.path.exists(os.path.join(task_directory, 'nodefile')):
            with open(os.path.join(task_directory, 'nodefile')) as f:
                self.node_editor.setPlainText(f.read())
        if os.path.exists(os.path.join(task_directory, 'nxserver.pid')):
            self.checkbox['server'].setChecked(True)
        if os.path.exists(os.path.join(task_directory, 'nxwatcher.pid')):
            self.checkbox['watcher'].setChecked(True)
        if os.path.exists(os.path.join(task_directory, 'nxlogger.pid')):
            self.checkbox['logger'].setChecked(True)

    def accept(self):
        if not self.home_directory:
            raise NeXusError('Experiment directory not chosen')
        try:
            with open(os.path.join(self.home_directory, 'tasks', 'nodefile'), 'w') as f:
                f.write(self.node_editor.toPlainText())
            switches = '-c %s -g %s' % (os.path.dirname(self.home_directory),
                                        os.path.basename(self.home_directory))
            if self.checkbox['server'].isChecked():
                subprocess.run('nxserver %s start' % switches, shell=True)
            else:
                subprocess.run('nxserver %s stop' % switches, shell=True)
            if self.checkbox['watcher'].isChecked():
                subprocess.run('nxwatcher %s start' % switches, shell=True)
            else:
                subprocess.run('nxwatcher %s stop' % switches, shell=True)
            if self.checkbox['logger'].isChecked():
                subprocess.run('nxlogger %s start' % switches, shell=True)
            else:
                subprocess.run('nxlogger %s stop' % switches, shell=True)
            super(ServerDialog, self).accept()
        except Exception as error:
            report_error("Managing Servers", error)
