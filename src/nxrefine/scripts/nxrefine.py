import argparse
from nxrefine.nxreduce import NXReduce


def main():

    parser = argparse.ArgumentParser(
        description="Refine lattice parameters and goniometer angles")
    parser.add_argument('-d', '--directory', required=True, 
                        help='scan directory')
    parser.add_argument('-e', '--entries', default=['f1', 'f2', 'f3'], 
        nargs='+', help='names of entries to be processed')
    parser.add_argument('-o', '--overwrite', action='store_true', 
                        help='overwrite existing maximum')

    args = parser.parse_args()

    for entry in args.entries:
        reduce = NXReduce(entry, args.directory, refine=True,
                          overwrite=args.overwrite)
        reduce.nxrefine()


if __name__=="__main__":
    main()
