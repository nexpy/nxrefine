import argparse
import os
import sys
from nxrefine.nxserver import NXServer

def main():

    parser = argparse.ArgumentParser(
        description="Launch server for data reduction workflow")
    parser.add_argument('-c', '--cwd', default='/nfs/chess/id4baux',
                        help='directory containing experiment directories')
    parser.add_argument('-e', '--exp', default='osborn-888-1',
                        help='Experiment name, e.g., osborn-888-1')
    parser.add_argument('-d', '--directory', nargs='?', const='.',
                        help='If specified, start the server in this directory, \
                        overriding other options')
    parser.add_argument('command', action='store',
                        help='valid commands are: status|start|stop|restart|clear')

    args = parser.parse_args()

    if args.directory:
        server = NXServer(os.path.realpath(args.directory))
    else:
        server = NXServer(os.path.join(args.cwd, args.gup))

    if args.command == 'status':
        print(server.status())
    elif args.command == 'start':
        server.start()
    elif args.command == 'stop':
        server.stop()
    elif args.command == 'restart':
        server.restart()
    elif args.command == 'clear':
        server.clear()


if __name__=="__main__":
    main()
