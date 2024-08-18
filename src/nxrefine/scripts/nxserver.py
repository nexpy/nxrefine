#!/usr/bin/env python
# -----------------------------------------------------------------------------
# Copyright (c) 2022, Argonne National Laboratory.
#
# Distributed under the terms of an Open Source License.
#
# The full license is in the file LICENSE.pdf, distributed with this software.
# -----------------------------------------------------------------------------

import argparse
from pathlib import Path

from nxrefine.nxserver import NXServer


def main():

    parser = argparse.ArgumentParser(
        description="Launch server for data reduction workflow")
    parser.add_argument('-d', '--directory', nargs='?', const='.',
                        help='Start the server in this directory')
    parser.add_argument('-t', '--type',
                        help='Server type: multicore|multinode|none')
    parser.add_argument('-n', '--nodes', default=[], nargs='+',
                        help='Add nodes')
    parser.add_argument('-c', '--cores', help='Number of cores')
    parser.add_argument('-r', '--remove', default=[], nargs='+',
                        help='Remove nodes')
    parser.add_argument(
        'command', action='store', nargs='?',
        help='valid commands are: status|start|stop|list|clear|kill')

    args = parser.parse_args()

    directory = Path(args.directory) if args.directory else None
    if directory:
        server = NXServer(directory=directory.resolve(),
                          server_type=args.type)
    elif args.type:
        server = NXServer(server_type=args.type)
    else:
        server = NXServer()

    if server.server_type == 'multinode':
        server.write_nodes(args.nodes)
        server.remove_nodes(args.remove)
    elif args.cores:
        server.set_cores(args.cores)

    if args.command == 'status':
        print(server.status())
    elif args.command == 'start':
        server.start()
    elif args.command == 'list':
        print(','.join(server.read_nodes()))
    elif args.command == 'stop':
        server.stop()
    elif args.command == 'restart':
        server.restart()
    elif args.command == 'clear':
        server.clear()
    elif args.command == 'kill':
        server.kill()
    elif args.command == 'status':
        if server.is_running():
            print(f"Server is running (pid={server.get_pid()})")
        else:
            print("Server is not running")


if __name__ == "__main__":
    main()
