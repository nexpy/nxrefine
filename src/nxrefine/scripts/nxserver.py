import argparse
import os
import sys
from nxrefine.nxserver import NXServer

def main():

    parser = argparse.ArgumentParser(
        description="Launch server for data reduction workflow")
    parser.add_argument('-c', '--cwd', default='/data/user6idd/dm',
                        help='directory containing GUP directories')
    parser.add_argument('-g', '--gup', default='GUP-58981',
                        help='GUP number, e.g., GUP-58981')
    parser.add_argument('-d', '--directory', nargs='?', const='.',
                        help='If specified, start the server in this directory, \
                        overriding other options')
    parser.add_argument('command', action='store',
                        help='valid commands are: start|stop|restart|clear')

    args = parser.parse_args()

    if args.directory:
        server = NXServer(os.path.realpath(args.directory))
    else:
        server = NXServer(os.path.join(args.cwd, args.gup))

    if args.command == 'start':
        server.start()
    elif args.command == 'stop':
        server.stop()
    elif args.command == 'restart':
        server.restart()
    elif args.command == 'clear':
        server.clear()


if __name__=="__main__":
    main()
