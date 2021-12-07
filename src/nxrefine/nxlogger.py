# -----------------------------------------------------------------------------
# Copyright (c) 2013-2021, NeXpy Development Team.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file COPYING, distributed with this software.
# -----------------------------------------------------------------------------

import logging
import logging.handlers
import os
import pickle
import struct
from socketserver import StreamRequestHandler, ThreadingTCPServer

from .daemon import NXDaemon


class LogRecordStreamHandler(StreamRequestHandler):
    """Handler for a streaming logging request.

    This basically logs the record using whatever logging policy is
    configured locally.
    """
    def handle(self):
        """
        Handle multiple requests - each expected to be a 4-byte length,
        followed by the LogRecord in pickle format. Logs the record
        according to whatever policy is configured locally.
        """
        while True:
            chunk = self.connection.recv(4)
            if len(chunk) < 4:
                break
            slen = struct.unpack('>L', chunk)[0]
            chunk = self.connection.recv(slen)
            while len(chunk) < slen:
                chunk = chunk + self.connection.recv(slen - len(chunk))
            obj = self.unPickle(chunk)
            record = logging.makeLogRecord(obj)
            self.handleLogRecord(record)

    def unPickle(self, data):
        return pickle.loads(data)

    def handleLogRecord(self, record):
        # if a name is specified, we use the named logger rather than the one
        # implied by the record.
        if self.server.logname is not None:
            name = self.server.logname
        else:
            name = record.name
        logger = logging.getLogger(name)
        if not logger.hasHandlers():
            handler = logging.FileHandler(self.server.log_file)
            formatter = logging.Formatter(
                            '%(asctime)s %(name)-12s: %(message)s',
                            datefmt='%Y-%m-%d %H:%M:%S')
            handler.setFormatter(formatter)
            logger.addHandler(handler)
        # N.B. EVERY record gets logged. This is because Logger.handle
        # is normally called AFTER logger-level filtering. If you want
        # to do filtering, do it at the client end to save wasting
        # cycles and network bandwidth!
        logger.handle(record)


class NXLogger(ThreadingTCPServer, NXDaemon):
    """
    Simple TCP socket-based logging receiver.
    """

    allow_reuse_address = True

    def __init__(self, directory, host='localhost',
                 port=logging.handlers.DEFAULT_TCP_LOGGING_PORT,
                 handler=LogRecordStreamHandler):
        self.pid_name = 'nxlogger'
        self.directory = directory
        self.task_directory = os.path.join(directory, 'tasks')
        if 'tasks' not in os.listdir(directory):
            os.mkdir(self.task_directory)
        self.log_file = os.path.join(self.task_directory, 'nxlogger.log')
        self.pid_file = os.path.join(self.task_directory, 'nxlogger.pid')
        NXDaemon.__init__(self, self.pid_name, self.pid_file)

        self.host = host
        self.port = port
        self.handler = handler

    def run(self):

        ThreadingTCPServer.__init__(self, (self.host, self.port), self.handler)
        self.abort = 0
        self.timeout = 1
        self.logname = None

        import select
        abort = 0
        while not abort:
            rd, wr, ex = select.select([self.socket.fileno()],
                                       [], [],
                                       self.timeout)
            if rd:
                self.handle_request()
            abort = self.abort

    def stop(self):
        self.abort = 1
        NXDaemon.stop(self)
