#!/usr/bin/env python
# -----------------------------------------------------------------------------
# Copyright (c) 2018-2021, NeXpy Development Team.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file COPYING, distributed with this software.
# -----------------------------------------------------------------------------

import argparse
import os

from nxrefine.nxserver import NXServer


def main():

    parser = argparse.ArgumentParser(
        description="Launch server for data reduction workflow")
    parser.add_argument('-d', '--directory', nargs='?', const='.',
                        help='Start the server in this directory')
    parser.add_argument('-t', '--type',
                        help='Server type: multicore|multinode')
    parser.add_argument('-n', '--nodes', default=[], nargs='+',
                        help='Add nodes')
    parser.add_argument('-c', '--cores', help='Number of cores')
    parser.add_argument('-r', '--remove', default=[], nargs='+',
                        help='Remove nodes')
    parser.add_argument('-s', '--sequential', action='store_true',
                        help='Use sequential (rather than parallel) processes')
    parser.add_argument(
        'command', action='store', nargs='?',
        help='valid commands are: status|start|stop|list|clear|kill')

    args = parser.parse_args()
    
    if args.sequential:
        sequential = True
    else:
        sequential = None

    if args.directory:
        server = NXServer(directory=os.path.realpath(args.directory),
                          server_type=args.type)
    elif args.type:
        server = NXServer(server_type=args.type, sequential=sequential)
    else:
        server = NXServer(sequential=sequential)

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
