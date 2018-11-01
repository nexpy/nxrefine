import argparse
from nxrefine.nxrefine import NXReduce


def main():

    parser = argparse.ArgumentParser(
        description="Find peaks within the NeXus data")
    parser.add_argument('-d', '--directory', required=True,
                        help='directory containing summed files')
    parser.add_argument('-e', '--entries', default=['f1', 'f2', 'f3'],
        nargs='+', help='names of entries to be summed')
    parser.add_argument('-s', '--scans', nargs='+', required=True,
                        help='list of scan directories to be summed')
    parser.add_argument('-o', '--overwrite', action='store_true',
                        help='overwrite existing peaks')

    args = parser.parse_args()
    
    for entry in args.entries:
        reduce = NXReduce(entry, args.directory, overwrite=args.overwrite)
        reduce.nxsum(args.scans)


if __name__=="__main__":
    main()

