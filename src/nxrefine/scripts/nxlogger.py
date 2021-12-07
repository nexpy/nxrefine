import argparse
import os

from nxrefine.nxlogger import NXLogger


def main():

    parser = argparse.ArgumentParser(
        description="Launch logger for data reduction workflow")
    parser.add_argument('-c', '--cwd', default='/data/user6idd/dm',
                        help='directory containing GUP directories')
    parser.add_argument('-g', '--gup', default='GUP-58981',
                        help='GUP number, e.g., GUP-58981')
    parser.add_argument('command', action='store',
                        help='valid commands are: start|stop|restart')

    args = parser.parse_args()

    logger = NXLogger(os.path.join(args.cwd, args.gup))

    if args.command == 'start':
        logger.start()
    elif args.command == 'stop':
        logger.stop()
    elif args.command == 'restart':
        logger.restart()


if __name__ == "__main__":
    main()
