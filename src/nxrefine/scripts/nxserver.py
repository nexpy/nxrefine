#!/usr/bin/env python
# -----------------------------------------------------------------------------
# Copyright (c) 2018-2025, Argonne National Laboratory.
#
# Distributed under the terms of an Open Source License.
#
# The full license is in the file LICENSE.pdf, distributed with this software.
# -----------------------------------------------------------------------------

"""Command line interface to the NXRefine workflow server.

OpenBLAS is held to one thread before NumPy is imported. The server does
no numerical work itself, but every process Parsl spawns re-imports this
module, and on a login node with many cores each of them would otherwise
start a thread per core and exhaust the limit on tasks before the server
had started. Setting it here rather than in the environment means the
server no longer depends on the shell it is launched from.
"""

import argparse
import os
import sys
from pathlib import Path

os.environ.setdefault('OPENBLAS_NUM_THREADS', '1')

from nexusformat.nexus import NeXusError  # noqa: E402

from nxrefine.nxserver import NXServer  # noqa: E402


def main():

    parser = argparse.ArgumentParser(
        description="Launch server for data reduction workflow")
    parser.add_argument('-d', '--directory', nargs='?', const='.',
                        help='Start the server in this directory')
    parser.add_argument('-t', '--type',
                        help='Server type: multicore|multinode|direct')
    parser.add_argument('-c', '--cores', help='Number of cores')
    parser.add_argument('-f', '--foreground', action='store_true',
                        help='Run the server in this terminal, not as a '
                             'daemon')
    parser.add_argument(
        'command', action='store', nargs='?',
        help='valid commands are: status|start|stop|clear|kill')

    args = parser.parse_args()

    directory = Path(args.directory) if args.directory else None
    if directory:
        server = NXServer(directory=directory.resolve(),
                          server_type=args.type)
    elif args.type:
        server = NXServer(server_type=args.type)
    else:
        server = NXServer()

    if args.cores:
        server.set_cores(args.cores)

    if args.command == 'status' or args.command is None:
        print(server.status())
    elif args.command == 'start':
        try:
            if args.foreground:
                server.run_foreground()
            else:
                server.start()
        except NeXusError as error:
            print(f'nxserver: {error}', file=sys.stderr)
            sys.exit(1)
    elif args.command == 'stop':
        server.stop()
    elif args.command == 'restart':
        server.restart()
    elif args.command == 'clear':
        server.clear()
    elif args.command == 'kill':
        server.kill()


if __name__ == "__main__":
    main()
