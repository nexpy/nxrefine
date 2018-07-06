import argparse
from nxrefine.nxreduce import NXReduce


def main():

    parser = argparse.ArgumentParser(
        description="Find peaks within the NeXus data")
    parser.add_argument('-d', '--directory', required=True,
                        help='scan directory')
    parser.add_argument('-e', '--entries', default=['f1', 'f2', 'f3'],
        nargs='+', help='names of entries to be searched')
    parser.add_argument('-t', '--threshold', type=float,
                        help='peak threshold - defaults to maximum counts/10')
    parser.add_argument('-f', '--first', type=int, help='first frame')
    parser.add_argument('-l', '--last', type=int, help='last frame')
    parser.add_argument('-o', '--overwrite', action='store_true',
                        help='overwrite existing peaks')
    parser.add_argument('-p', '--parent', default=None,
                        help='The parent .nxs file to use')

    args = parser.parse_args()

    for entry in args.entries:
        reduce = NXReduce(entry, args.directory, find=True,
                          threshold=args.threshold,
                          first=args.first, last=args.last,
                          overwrite=args.overwrite)
        reduce.nxfind()


if __name__=="__main__":
    main()
