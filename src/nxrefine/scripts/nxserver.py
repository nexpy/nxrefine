import argparse
import os
import sys
from nxrefine.nxserver import NXServer

def main():

    parser = argparse.ArgumentParser(
        description="Launch server for data reduction workflow")
    parser.add_argument('-d', '--directory', nargs='?', const='.',
                        help='Start the server in this directory')
    parser.add_argument('-t', '--type', help='Server type: multicore|multinode')
    parser.add_argument('-n', '--nodes', default=[], nargs='+', 
                        help='Add nodes')
    parser.add_argument('-r', '--remove', default=[], nargs='+', 
                        help='Remove nodes')
    parser.add_argument('command', action='store', nargs='?',
        help='valid commands are: status|start|list|stop|restart|clear')

    args = parser.parse_args()

    if args.directory:
        server = NXServer(directory=os.path.realpath(args.directory),
                          server_type=args.type)
    elif args.type:
        server = NXServer(server_type=args.type)
    else:
        server = NXServer()

    if server.server_type == 'multinode':
        server.write_nodes(args.nodes)
        server.remove_nodes(args.remove)

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
        if args.gup:
            server.clear(os.path.join(args.cwd, args.gup))
        else:
            server.clear()
    elif args.command == 'status':
        if server.is_running():
            print("Server is running (pid=%s)" % server.get_pid())
        else:
            print("Server is not running")


if __name__=="__main__":
    main()
