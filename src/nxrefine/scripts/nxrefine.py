import argparse
from nxrefine.nxreduce import NXReduce


def main():

    parser = argparse.ArgumentParser(
        description="Refine lattice parameters and goniometer angles")
    parser.add_argument('-d', '--directory', required=True, 
                        help='scan directory')
    parser.add_argument('-e', '--entries', default=['f1', 'f2', 'f3'], 
        nargs='+', help='names of entries to be processed')
    parser.add_argument('-l', '--lattice', action='store_true',
                        help='refine lattice parameters')
    parser.add_argument('-o', '--overwrite', action='store_true', 
                        help='overwrite existing maximum')
    parser.add_argument('-q', '--queue', action='store_true',
                        help='add to server task queue')

    args = parser.parse_args()

    for i, entry in enumerate(args.entries):
        if i == 0:
            lattice = args.lattice
        else:
            lattice = False
        reduce = NXReduce(entry, args.directory, refine=True,
                          lattice=lattice, overwrite=args.overwrite)
        if args.queue:
            reduce.queue()
        else:
            reduce.nxrefine()


if __name__=="__main__":
    main()
