import argparse
import os
import sys
from nxrefine.nxwatcher import NXWatcher


def main():

    parser = argparse.ArgumentParser(
        description="Launch watcher to monitor new files")
    parser.add_argument('-c', '--cwd', default='/data/user6idd/dm', 
                        help='directory containing GUP directories')
    parser.add_argument('-g', '--gup', default='GUP-58981',
                        help='GUP number, e.g., GUP-58981')
    parser.add_argument('-e', '--entries', nargs='+', 
                        help='names of entries to be processed')
    parser.add_argument('-t', '--timeout', default=120,
                        help='Time elapsed before initiating action')
    parser.add_argument('command', action='store',
                         help='valid commands are: start|stop|restart')
    
    args = parser.parse_args()

    if args.entries:
        entries = args.entries
    else:
        entries = NXMultiReduce(args.directory).entries

    server = NXWatcher(os.path.join(args.cwd, args.gup), 
                       entries=entries, timeout=args.timeout)
    
    if args.command == 'start':
        server.start()
    elif args.command == 'stop':
        server.stop()
    elif args.command == 'restart':
        server.restart()
    else:
        print("Unknown command")
        sys.exit(2)
    sys.exit(0)


if __name__=="__main__":
    main()
