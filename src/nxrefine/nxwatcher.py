import time
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from .daemon import NXDaemon
from .nxserver import NXServer
from .nxreduce import NXReduce


class NXWatcher(NXDaemon):

    def __init__(self, directory):
        self.directory = directory
        self.task_directory = os.path.join(self.directory, 'tasks')
        if 'tasks' not in os.listdir(self.directory):
            os.mkdir(self.task_directory)
        self.server = NXServer(self.directory)
        self.watch_files = {}
        self.pid_file = os.path.join(self.task_directory, 'nxwatcher.pid')
        self.observer = Observer()
        super(NXWatcher, self).__init__(self.pid_file)

    def run(self):
        event_handler = NXHandler(self.server)
        self.observer.schedule(event_handler, self.directory, recursive=True)
        self.observer.start()
        try:
            while True:
                time.sleep(10)
        except:
            self.observer.stop()
        self.observer.join()


class NXHandler(FileSystemEventHandler):

    def __init__(self, server):
        self.server = server
        super(NXHandler, self).__init__()

    @staticmethod
    def on_any_event(event):
        if event.is_directory:
            return None
        elif event.event_type == 'created':
            if event.src_path.endswith('.h5'):
                self.watch_files[event.src_path] = time.time()
        elif event.event_type == 'modified':
            if event.src_path in self.watch_files:
                now = time.time()
                if now - self.watch_files[event.src_path] > 120.0:
                    reduce = NXReduce(entry, os.path.dirname(event.src_path))
                    self.server.add_task('nxtask ')
                    del self.watch_files[event.src_path]
                else:
                    self.watch_files[event.src_path] = time.time()
