import argparse
from nxrefine.nxdatabase import sync_db

def main():
    parser = argparse.ArgumentParser(description="Populate the database based \
            on local NeXus files")
    parser.add_argument('-d', required=True, dest='directory',
                        help='The directory of the sample to sync')
    # parser.add_argument('sync', action='store_true',
    #                     help="Specify 'sync' to sync local files with the database")

    args = parser.parse_args()
    if args.sync:
        print('Looking in directory {}'.format(args.directory))
        sync_db(args.directory)

if __name__ == "__main__":
    main()
