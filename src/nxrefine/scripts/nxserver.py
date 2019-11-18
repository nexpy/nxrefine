import argparse
import os
import sys
from nxrefine.nxserver import NXServer

def main():

    parser = argparse.ArgumentParser(
        description="Launch server for data reduction workflow")
    parser.add_argument('-c', '--cwd', default='/data/user6idd/dm',
                        help='directory containing GUP directories')
    parser.add_argument('-g', '--gup', help='GUP number, e.g., GUP-58981')
    parser.add_argument('-d', '--directory', nargs='?', const='.',
                        help='Start the server in this directory')
    parser.add_argument('command', action='store',
        help='valid commands are: start|stop|restart|clear|status|add')

    args = parser.parse_args()

    if args.directory:
        server = NXServer(os.path.realpath(args.directory))
    else:
        server = NXServer()

    if args.command == 'start':
        server.start()
    elif args.command == 'stop':
        server.stop()
    elif args.command == 'restart':
        server.restart()
    elif args.command == 'clear':
        if args.gup:
            server.clear(os.path.join(args.cwd, args.gup))
        else:
            server.clear()
    elif args.command == 'status':
        if server.is_running():
            print("Server is running (pid=%s)" % server.get_pid())
        else:
            print("Server is not running")
    elif args.command == 'add':
        server.register(os.path.join(args.cwd, args.gup))


if __name__=="__main__":
    main()
