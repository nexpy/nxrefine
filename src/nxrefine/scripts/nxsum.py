import argparse
import os
import sys
import timeit
import h5py as h5
from nexusformat.nexus import *
from nxrefine.nxlock import Lock
from nxrefine.nxserver import NXServer

def sum(directory, new_scan, entries, scans):

    tic = timeit.default_timer()

    nframes = 3650
    chunk_size = 200

    for entry in entries:
        new_name = os.path.join(directory, new_scan, entry+'.h5')
        new_file = h5.File(new_name, 'r+')
        new_field = new_file['/entry/data/data']
        for scan in scans:
            print('Adding', scan)
            scan_name = os.path.join(directory, scan, entry+'.h5')
            with Lock(scan_name):
                scan_file = h5.File(scan_name, 'r')
                scan_field = scan_file['/entry/data/data']
                for i in range(0, nframes, chunk_size):
                    print(entry, i)
                    new_slab = new_field[i:i+chunk_size,:,:]
                    scan_slab = scan_field[i:i+chunk_size,:,:]
                    try:
                        new_field[i:i+chunk_size,:,:] = new_slab + scan_slab
                    except IndexError as error:
                        pass
            toc = timeit.default_timer()
            print(toc-tic, 'seconds')
    
    toc = timeit.default_timer()
    print(toc-tic, 'seconds')

def main():

    parser = argparse.ArgumentParser(
        description="Find peaks within the NeXus data")
    parser.add_argument('-d', '--directory', required=True,
                        default='/data/user6idd/dm/GUP-58924_run18-3/LBCOx0125/xtal1',
                        help='directory containing wrapper files')
    parser.add_argument('-n', '--new_scan', default='30K_sum',
                        help='scan directory to contain sum')
    parser.add_argument('-e', '--entries', default=['f1', 'f2', 'f3'],
        nargs='+', help='names of entries to be searched')
    parser.add_argument('-s', '--scans', nargs='+',
                        default=['30K_%s' % i for i in range(2,9)],
                        help='list of scan directories to be summed')

    args = parser.parse_args()

    sum(args.directory, args.new_scan, args.entries, args.scans)

if __name__=="__main__":
    main()

