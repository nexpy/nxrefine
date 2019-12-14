import argparse
import os
from nxrefine.nxdatabase import NXDatabase

def main():
    parser = argparse.ArgumentParser(description="Populate the database based \
            on local NeXus files")
    parser.add_argument('-d', '--directory', required=True,
                        help='scan directory')

    args = parser.parse_args()

    dir = os.path.realpath(args.directory)
    print('Looking in directory {}'.format(dir))
    db_path = os.path.join(os.path.dirname(os.path.dirname(dir)), 'tasks',
                           'nxdatabase.db')
    nxdb = NXDatabase(db_path)
    nxdb.sync_db(args.directory)

if __name__ == "__main__":
    main()
