import argparse
import os
import nxrefine.nxdatabase as nxdb

def main():
    parser = argparse.ArgumentParser(description="Populate the database based \
            on local NeXus files")
    parser.add_argument('dir', nargs='?', default='.', help="The directory \
            containing the wrapper files of the sample to sync")
    parser.add_argument('-f', '--database-file', default='NXdatabase.db',
            help='The name of the file in which to save the database')

    args = parser.parse_args()

    dir = os.path.realpath(args.dir)
    print('Looking in directory {}'.format(dir))
    db_path = os.path.join(os.path.dirname(os.path.dirname(dir)), 'NXdatabase.db')
    nxdb.init('sqlite:///' + db_path)
    nxdb.sync_db(args.dir)

if __name__ == "__main__":
    main()
