# -----------------------------------------------------------------------------
# Copyright (c) 2018-2026, Argonne National Laboratory.
#
# Distributed under the terms of an Open Source License.
#
# The full license is in the file LICENSE.pdf, distributed with this software.
# -----------------------------------------------------------------------------

"""Server that dispatches NXRefine workflow tasks through Parsl.

Tasks are shell commands, normally one `nxreduce` invocation covering
every entry in a scan. They are submitted either one at a time with
`NXServer.add_task` or as a batch with `NXServer.submit_batch`, which
records the size of the batch so that the dispatcher can choose an
appropriate allocation for it.

Three server types are supported. In `direct` mode, commands run in
this process as they are submitted. In `multicore` and `multinode`
modes, they are written to a file queue and dispatched by a daemon,
which is what allows a task to be queued while the server is down.

The Parsl configuration itself lives in `nxrefine.nxparsl`, or in the
site-specific module named by the `config` setting in the `[parsl]`
section.
"""

import os
import shutil
import sqlite3
import time
import uuid
from configparser import ConfigParser
from datetime import datetime
from pathlib import Path
from queue import Empty, Queue

import psutil
from nexusformat.nexus import NeXusError, NXLock
from persistqueue import Queue as FileQueue
from persistqueue.exceptions import Empty as FileEmpty
from persistqueue.serializers import json

from .nxdaemon import NXDaemon
from .nxparsl import import_config
from .nxsettings import NXSettings

POLL_INTERVAL = 5


def get_servers():
    """Return a list of available server types

    Returns
    -------
    list of str
        Names of valid server types
    """
    return ['direct', 'multicore', 'multinode']


class NXFileQueue(FileQueue):
    """A file-based queue with locked access.

    Items are stored as dictionaries carrying the command and, when the
    command was submitted as part of a batch, the identity and size of
    that batch. Bare strings written by an earlier version are still
    read correctly.
    """

    def __init__(self, directory, autosave=False):
        """
        Create a file-based queue with locked access.

        Parameters
        ----------
        directory : str or Path
            Path to the directory for the queue.
        autosave : bool, optional
            Autosave the queue after every put or get operation, by
            default False
        """
        self.directory = Path(directory)
        self.directory.mkdir(mode=0o777, exist_ok=True)
        tempdir = self.directory / 'tempdir'
        tempdir.mkdir(mode=0o777, exist_ok=True)
        self.lock = NXLock(self.directory / 'filequeue')
        with self.lock:
            super().__init__(directory, serializer=json, autosave=autosave,
                             tempdir=tempdir)
            self.fix_access()

    def __repr__(self):
        return f"NXFileQueue('{self.directory}')"

    def __enter__(self):
        self.lock.acquire()
        self.info = self._loadinfo()

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.fix_access()
        self.lock.release()

    def put(self, item, block=True, timeout=None):
        """Add an NXTask, or a bare command, to the queue."""
        if isinstance(item, NXTask):
            item = item.payload()
        elif not isinstance(item, dict):
            item = {'command': str(item)}
        with self:
            super().put(item, block=block, timeout=timeout)

    def get(self, block=True, timeout=None):
        """Return the next item in the queue as an NXTask."""
        with self:
            item = super().get(block=block, timeout=timeout)
        return NXTask.from_payload(item)

    def queued_tasks(self):
        """Return the NXTasks still remaining in the queue."""
        with self:
            tasks = []
            while self.qsize() > 0:
                tasks.append(NXTask.from_payload(super().get(timeout=0)))
        return tasks

    def fix_access(self):
        """Ensure that the file queue pointer is readable."""
        for f in [f for f in self.directory.iterdir() if f.is_file()]:
            try:
                self.directory.joinpath(f).chmod(0o666)
            except Exception:
                pass
        for f in [f for f in self.directory.iterdir() if f.is_dir()]:
            try:
                self.directory.joinpath(f).chmod(0o777)
            except Exception:
                pass


class NXTask:
    """A command waiting to be dispatched.

    Attributes
    ----------
    command : str
        The shell command to be run.
    batch_id : str or None
        Identifies the batch the command was submitted with, so that
        the grouping survives a restart of the server.
    batch_size : int
        Number of commands in that batch, used to choose the executor.
    """

    def __init__(self, command, batch_id=None, batch_size=1):
        self.command = str(command)
        self.name = self.command.split()[0] if self.command else ''
        self.batch_id = batch_id
        self.batch_size = batch_size

    def __repr__(self):
        return f"NXTask('{self.name}')"

    @classmethod
    def from_payload(cls, payload):
        """Return an NXTask read from a queue entry."""
        if isinstance(payload, dict):
            return cls(payload.get('command', ''),
                       batch_id=payload.get('batch_id'),
                       batch_size=payload.get('batch_size', 1))
        return cls(payload)

    def payload(self):
        """Return this task as a queue entry."""
        return {'command': self.command, 'batch_id': self.batch_id,
                'batch_size': self.batch_size}

    def argument(self, switches):
        """Return the values following the first switch that is present.

        Parameters
        ----------
        switches : list of str
            Equivalent spellings of the switch, such as
            `['--directory', '-d']`.

        Returns
        -------
        list of str
            Words between the switch and the next one, which is empty
            if the switch does not appear in the command.
        """
        words = self.command.split()
        for switch in switches:
            if switch in words[:-1]:
                values = []
                for word in words[words.index(switch)+1:]:
                    if word.startswith('-'):
                        break
                    values.append(word)
                return values
        return []

    @property
    def label(self):
        """Return a name identifying this task in its log files.

        Parsl names the logs after the app function, which is the same
        for every command, so the scan and its entries are used instead.
        That makes both the files and the rows pointing at them in the
        monitoring database identifiable.
        """
        parts = [self.name]
        directory = self.argument(['--directory', '-d'])
        if directory:
            parts.extend(Path(directory[0]).parts[-2:])
        parts.extend(self.argument(['--entries', '-e']))
        return '_'.join(parts)


class NXServer(NXDaemon):

    def __init__(self, directory=None, server_type=None):
        self.pid_name = 'nxserver'
        self.initialize(directory, server_type)
        self._task_queue = None
        self._config = None
        self._module = None
        self._apps = None
        self.tasks = {}
        self.prefixes = set()
        if self.server_type != 'direct':
            super(NXServer, self).__init__(self.pid_name, self.pid_file)

    def __repr__(self):
        return f"NXServer(directory='{self.directory}')"

    def get_directory(self):
        home_settings_file = Path.home() / '.nxserver' / 'settings.ini'
        if 'NX_SERVER' in os.environ:
            return Path(os.environ['NX_SERVER'])
        elif home_settings_file.exists():
            home_settings = ConfigParser()
            home_settings.read(home_settings_file)
            if home_settings.has_option('setup', 'directory'):
                return Path(home_settings.get('setup', 'directory'))
        else:
            return None

    def save_directory(self):
        Path.home().joinpath('.nxserver').mkdir(exist_ok=True)
        home_settings_file = Path.home() / '.nxserver' / 'settings.ini'
        home_settings = ConfigParser()
        if home_settings_file.exists():
            home_settings.read(home_settings_file)
        if 'setup' not in home_settings.sections():
            home_settings.add_section('setup')
        home_settings.set('setup', 'directory', str(self.directory))
        with open(home_settings_file, 'w') as f:
            home_settings.write(f)

    def initialize(self, directory, server_type):
        if directory is None:
            self.settings = NXSettings(directory=self.get_directory())
            self.directory = self.settings.directory
        else:
            self.settings = NXSettings(directory=directory)
            self.directory = self.settings.directory
            self.save_directory()
        if server_type:
            if server_type == 'None' or server_type == 'none':
                server_type = 'direct'
            self.server_type = server_type
            self.settings.set('server', 'type', server_type)
            self.settings.save()
        elif self.settings.has_option('server', 'type'):
            self.server_type = self.settings.get('server', 'type')
            if self.server_type == 'None' or self.server_type == 'none':
                self.server_type = 'direct'
        else:
            self.server_type = 'direct'
        if self.server_type == 'multinode':
            self.cpus = []
        else:
            if self.settings.has_option('server', 'cores'):
                cpu_count = int(self.settings.get('server', 'cores'))
                if cpu_count > psutil.cpu_count():
                    cpu_count = psutil.cpu_count()
            else:
                cpu_count = psutil.cpu_count()
            self.cpus = ['cpu'+str(cpu) for cpu in range(1, cpu_count+1)]
        self.concurrent = self.settings.get('server', 'concurrent')
        self.server_log = self.directory / 'nxserver.log'
        self.pid_file = self.directory / 'nxserver.pid'
        self.queue_directory = self.directory / 'task_list'
        self.parsl_directory = self.directory / 'parsl'
        self.log_directory = self.parsl_directory / 'task_logs'
        self.monitoring_db = self.parsl_directory / 'monitoring.db'

    @property
    def task_queue(self):
        if self._task_queue is None:
            if self.server_type == 'direct':
                self._task_queue = Queue()
            else:
                self._task_queue = NXFileQueue(self.queue_directory,
                                               autosave=True)
        return self._task_queue

    @property
    def parsl_options(self):
        """Settings passed to the Parsl configuration functions."""
        options = {}
        if 'parsl' in self.settings.sections():
            options = {option: self.settings.get('parsl', option)
                       for option in self.settings.options('parsl')}
        options['server_type'] = self.server_type
        options['cores'] = len(self.cpus) or 1
        return options

    def read_nodes(self):
        """Return the list of nodes.

        Nodes are allocated by the batch scheduler, so this is always
        empty. It is retained because the server CLI and the Manage
        Server dialog still call it.
        """
        return []

    def write_nodes(self, nodes):
        """Log that nodes are no longer configured by the server."""
        if nodes:
            self.log("Nodes are allocated by the scheduler and cannot be set")

    def remove_nodes(self, nodes):
        """Log that nodes are no longer configured by the server."""
        if nodes:
            self.log("Nodes are allocated by the scheduler and cannot be set")

    def set_cores(self, cpu_count):
        """Select number of cores"""
        try:
            cpu_count = int(cpu_count)
        except ValueError:
            raise NeXusError('Number of cores must be a valid integer')
        self.settings.set('server', 'cores', cpu_count)
        self.settings.save()
        self.cpus = ['cpu'+str(cpu) for cpu in range(1, cpu_count+1)]

    def log(self, message):
        with NXLock(self.server_log, timeout=60, expiry=60):
            with open(self.server_log, 'a') as f:
                f.write(datetime.now().strftime("%Y-%m-%d %H:%M:%S") + ' ' +
                        str(message) + '\n')

    def load_parsl(self):
        """Load Parsl and define one bash app per executor.

        Parsl binds an app to its executors when the app is defined, so
        routing a command to a chosen allocation means holding a
        separate app for each executor label.
        """
        if self._apps is not None:
            return
        import parsl
        from parsl.app.app import bash_app

        module = import_config(self.settings.get('parsl', 'config')
                               if self.settings.has_option('parsl', 'config')
                               else None, self.directory)
        self._module = module
        self._config = module.get_config(self.parsl_options,
                                         self.parsl_directory)
        parsl.load(self._config)
        self._apps = {}
        for label in [executor.label for executor in self._config.executors]:
            @bash_app(executors=[label])
            def run_command(command, stdout=None, stderr=None):
                return command
            self._apps[label] = run_command

    def dispatch(self, task):
        """Submit a task to the executor chosen for its batch."""
        self.load_parsl()
        label = self._module.select_executor(self.parsl_options,
                                             task.batch_size)
        if label not in self._apps:
            self.log(f"No executor '{label}'; using '{list(self._apps)[0]}'")
            label = list(self._apps)[0]
        self.log(f"Submitting '{task.command}' to {label}")
        prefix = self.log_prefix(task)
        self.tasks[self._apps[label](task.command,
                                     stdout=str(prefix) + '.out',
                                     stderr=str(prefix) + '.err')] = task

    def log_prefix(self, task):
        """Return a path stem no other task's log files are using.

        The whole queue is normally dispatched within a single tick, so
        the timestamp alone does not separate one task's logs from the
        next one's. A task's output file also identifies it in the
        monitoring database, where a shared name would hide every row
        but the last.
        """
        stem = task.label + datetime.now().strftime('_%Y%m%d_%H%M%S')
        prefix = self.log_directory / stem
        count = 0
        while (prefix in self.prefixes
               or Path(str(prefix) + '.out').exists()):
            count += 1
            prefix = self.log_directory / f'{stem}_{count}'
        self.prefixes.add(prefix)
        return prefix

    def reap(self):
        """Log the outcome of any tasks that have finished."""
        for future in [f for f in self.tasks if f.done()]:
            task = self.tasks.pop(future)
            try:
                future.result()
                self.log(f"Completed '{task.command}'")
            except Exception as error:
                self.log(f"Failed '{task.command}': {error}")

    def task_status(self):
        """Return what Parsl monitoring records about each task.

        The records are keyed on the task's standard output file, which
        is the only field the monitoring database and the log directory
        have in common. An empty dictionary is returned when monitoring
        is disabled, which it is for the `direct` server type.

        Returns
        -------
        dict
            Executor, status and timestamps, keyed on output file.
        """
        if not self.monitoring_db.exists():
            return {}
        query = """
            SELECT task_stdout AS log,
                   task_time_invoked AS invoked,
                   task_time_returned AS returned,
                   (SELECT task_executor FROM try
                     WHERE try.run_id = task.run_id
                       AND try.task_id = task.task_id
                     ORDER BY try.try_id DESC LIMIT 1) AS executor,
                   (SELECT task_status_name FROM status
                     WHERE status.run_id = task.run_id
                       AND status.task_id = task.task_id
                     ORDER BY status.timestamp DESC LIMIT 1) AS status
            FROM task WHERE task_stdout IS NOT NULL
        """
        try:
            with sqlite3.connect(f'file:{self.monitoring_db}?mode=ro',
                                 uri=True) as db:
                db.row_factory = sqlite3.Row
                return {row['log']: {key: row[key] for key in row.keys()
                                     if key != 'log'}
                        for row in db.execute(query)}
        except sqlite3.Error:
            return {}

    def task_records(self, limit=50):
        """Return a summary of recently dispatched tasks, newest first.

        The tasks are listed from their log files, which are written
        whatever the server type, and annotated with what the Parsl
        monitoring database knows about them when it is available.

        Parameters
        ----------
        limit : int, optional
            Maximum number of tasks to list, by default 50.
        """
        if not self.log_directory.exists():
            return []
        logs = sorted((f for f in self.log_directory.iterdir()
                       if f.suffix == '.out'),
                      key=lambda f: f.stat().st_mtime, reverse=True)
        status = self.task_status()
        records = []
        for log in logs[:limit]:
            record = {'name': log.stem, 'stdout': log,
                      'stderr': log.with_suffix('.err')}
            record.update(status.get(str(log), {}))
            records.append(record)
        return records

    def task_names(self):
        """List the names of recently dispatched tasks, newest first."""
        return [record['name'] for record in self.task_records()]

    def task_output(self, name):
        """Return the output of a dispatched task.

        Parameters
        ----------
        name : str
            Name of the task, as listed by `task_names`.
        """
        record = next((record for record in self.task_records()
                       if record['name'] == name), None)
        if record is None:
            return f"No output for '{name}'"
        text = [' '.join(str(record[key]) for key in
                         ['executor', 'status', 'invoked', 'returned']
                         if record.get(key))]
        for key in ['stdout', 'stderr']:
            path = record[key]
            if path.exists() and path.stat().st_size:
                text.append(f'--- {path.name} ---')
                text.append(path.read_text())
        return '\n'.join(t for t in text if t) or f"No output for '{name}'"

    def run(self):
        """Dispatch commands read from the task queue.

        Any commands left in the queue when the server last stopped are
        resubmitted first, preserving their batch grouping. The loop
        then dispatches new commands until a 'stop' command is read.
        """
        self.log(f'Starting server (pid={os.getpid()})')
        try:
            self.load_parsl()
        except Exception as error:
            self.log(f"Could not configure Parsl: {error}")
            super(NXServer, self).stop()
            return
        stopped = False
        while not stopped:
            time.sleep(POLL_INTERVAL)
            while True:
                task = self.read_task()
                if task is None:
                    break
                elif task.command == 'stop':
                    stopped = True
                    break
                try:
                    self.dispatch(task)
                except Exception as error:
                    self.log(f"Could not submit '{task.command}': {error}")
            self.reap()
        self.log("Waiting for submitted tasks to finish")
        self.shutdown()
        self.log("Stopping server")
        super(NXServer, self).stop()

    def add_task(self, tasks, batch_id=None, batch_size=1):
        """Add one or more commands to the server queue.

        Parameters
        ----------
        tasks : str or list of str
            Commands to be queued, either as a list or separated by
            newlines.
        batch_id : str, optional
            Identifier shared by every command in a batch.
        batch_size : int, optional
            Number of commands in that batch, by default 1.
        """
        if isinstance(tasks, str):
            tasks = tasks.split('\n')
        queued = self.queued_tasks()
        for command in [task for task in tasks if task]:
            if command != 'stop' and command in queued:
                continue
            task = NXTask(command, batch_id=batch_id, batch_size=batch_size)
            if self.server_type == 'direct' and command != 'stop':
                self.dispatch(task)
            else:
                self.task_queue.put(task)
            queued.append(command)

    def submit_batch(self, commands):
        """Submit a group of commands to be run in one allocation.

        Recording the size of the batch is what allows the dispatcher
        to pick an allocation that fits it, so this should be preferred
        to calling `add_task` for each command in turn.

        Parameters
        ----------
        commands : list of str
            Commands to be queued, normally one per scan.

        Returns
        -------
        str or None
            The batch identifier, or None if there was nothing to do.
        """
        commands = [command for command in commands if command]
        if not commands:
            return None
        batch_id = uuid.uuid4().hex[:8]
        self.add_task(commands, batch_id=batch_id, batch_size=len(commands))
        return batch_id

    def read_task(self):
        """Read the next task from the server queue"""
        try:
            return self.task_queue.get(block=False)
        except (FileEmpty, Empty):
            return None
        except Exception as error:
            self.log(str(error))
            return None

    def remove_task(self, task):
        """Remove task from the server queue."""
        tasks = [t for t in self.pending_tasks() if t.command != task]
        self.clear()
        for t in tasks:
            self.add_task(t.command, batch_id=t.batch_id,
                          batch_size=t.batch_size)

    def pending_tasks(self):
        """List the NXTasks remaining on the server queue."""
        if self.server_type == 'direct':
            return list(self.task_queue.queue)
        queue = NXFileQueue(self.queue_directory, autosave=False)
        return queue.queued_tasks()

    def queued_tasks(self):
        """List the commands remaining on the server queue."""
        return [task.command for task in self.pending_tasks()]

    def status(self):
        if self.server_type == 'direct':
            return "Server is configured to run commands directly"
        else:
            return super(NXServer, self).status()

    def is_running(self):
        """
        Check if the server is running.

        If the server is running in direct mode, this is done by
        checking if Parsl has been loaded in this process. Otherwise, it
        is done by calling the NXDaemon class method.
        """
        if self.server_type == 'direct':
            return self._apps is not None
        else:
            return super(NXServer, self).is_running()

    def stop(self):
        """Stop the server when active tasks are completed."""
        if self.is_running():
            if self.server_type == 'direct':
                self.shutdown()
            else:
                self.add_task('stop')

    def shutdown(self):
        """Wait for tasks running in this process and unload Parsl."""
        if self._apps is None:
            return
        try:
            import parsl
            parsl.dfk().wait_for_current_tasks()
            self.reap()
            parsl.dfk().cleanup()
        except Exception as error:
            self.log(str(error))
        self._apps = None
        self._config = None

    def clear(self):
        """Clear the server queue."""
        if self.server_type == 'direct':
            self._task_queue = Queue()
        else:
            with self.task_queue.lock:
                if self.queue_directory.exists():
                    shutil.rmtree(self.queue_directory, ignore_errors=True)
            self._task_queue = NXFileQueue(self.queue_directory)

    def kill(self):
        """Kill the server process.

        This provides a backup mechanism for terminating the server if
        adding 'stop' to the task list does not work.
        """
        if self.server_type != 'direct':
            super(NXServer, self).stop()
