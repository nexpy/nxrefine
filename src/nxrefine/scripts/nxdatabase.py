import argparse
import nxrefine.nxdatabase as nxdb

def main():
    parser = argparse.ArgumentParser(description="Populate the database based \
            on local NeXus files")
    parser.add_argument('dir', help='The directory containing the wrapper files\
                        of the sample to sync')
    # parser.add_argument('sync', action='store_true',
    #                     help="Specify 'sync' to sync local files with the database")

    args = parser.parse_args()
    # if args.sync:
    nxdb.init('mysql+mysqlconnector://python:pythonpa^ss@18.219.38.132/test')
    print('Looking in directory {}'.format(args.dir))
    nxdb.sync_db(args.dir)

if __name__ == "__main__":
    main()
