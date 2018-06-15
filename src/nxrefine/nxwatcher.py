import os
import time
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from .daemon import NXDaemon
from .nxserver import NXServer
from .nxreduce import NXReduce


class NXWatcher(NXDaemon):

    def __init__(self, directory, entries=['f1', 'f2', 'f3'], timeout=120):
        self.directory = directory
        self.entries = entries
        self.timeout = timeout
        self.task_directory = os.path.join(self.directory, 'tasks')
        if 'tasks' not in os.listdir(self.directory):
            os.mkdir(self.task_directory)
        self.server = NXServer(self.directory)
        self.watch_files = {}
        self.log_file = os.path.join(self.task_directory, 'nxserver.log')
        self.pid_file = os.path.join(self.task_directory, 'nxwatcher.pid')
        self.observer = Observer()
        super(NXWatcher, self).__init__(self.pid_file)

    def run(self):
        event_handler = NXHandler(self.server, self.entries, self.timeout,
                                  self.log_file)
        self.observer.schedule(event_handler, self.directory, recursive=True)
        self.observer.start()
        try:
            while True:
                time.sleep(10)
        except:
            self.observer.stop()
        self.observer.join()


class NXHandler(FileSystemEventHandler):

    def __init__(self, server, entries, timeout, log_file):
        self.server = server
        self.entries = entries
        self.timeout = timeout
        self.log_file = log_file
        super(NXHandler, self).__init__()

    def log(self, message):
        with open(self.log_file, 'a') as f:
            f.write(message+'\n')

    def static(self, file_name):
        now = time.time()
        if file_name in self.watch_files:
            if now - self.watch_files[file_name] > self.timeout:
                return True
        return False

    @staticmethod
    def on_any_event(event):
        file_name = event.src_path
        self.log('watcher: Monitoring %s' % file_name)
        if event.is_directory:
            return None
        elif event.event_type == 'created':
            if file_name.endswith('.h5') or file_name.endswith('.nxs'):
                self.watch_files[file_name] = time.time()
        elif event.event_type == 'modified':
            if file_name in self.watch_files:
                if self.static(file_name):
                    entry = os.path.basename(file_name)[0:2]
                    directory = os.path.dirname(file_name)
                    if entry in self.entries:
                        if file_name.endswith('.h5'):
                            self.log('watcher: Queuing %s' % file_name)
                            reduce = NXReduce(entry, directory,
                                              link=True, maxcount=True)
                            if reduce.parent:
                                reduce.find = True
                                reduce.copy = True
                                reduce.refine = True
                                reduce.transform = True
                            reduce.queue()
                            del self.watch_files[file_name]
                        elif '_transform' in file_name:
                            self.log('Queuing %s' % file_name)
                            if (True not in 
                                [NXReduce(e, directory).not_complete('nxtransform')
                                 for e in self.entries]):
                                self.server.add_task('nxcombine -d %s' % directory)
                else:
                    self.watch_files[file_name] = time.time()

    def log(self, message):
        with open(self.log_file, 'a') as f:
            f.write(message+'\n')
