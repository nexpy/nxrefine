import argparse
import os
import sys
from nxrefine.nxserver import NXServer

def main():

    parser = argparse.ArgumentParser(
        description="Launch server for data reduction workflow")
    parser.add_argument('-c', '--cwd', default='/volt',
                        help='directory containing experiment directories')
    parser.add_argument('-e', '--exp', help='Experiment name, e.g., GUP-58981')
    parser.add_argument('-d', '--directory', nargs='?', const='.',
                        help='Start the server in this directory')
    parser.add_argument('command', action='store',
        help='valid commands are: status|start|stop|restart|clear|add')

    args = parser.parse_args()

    if args.directory:
        server = NXServer(os.path.realpath(args.directory))
    else:
        server = NXServer(os.path.join(args.cwd, 'nxserver'))

    if args.command == 'status':
        print(server.status())
    elif args.command == 'start':
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
        server.register(os.path.join(args.cwd, args.exp))


if __name__=="__main__":
    main()
