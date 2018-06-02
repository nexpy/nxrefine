import argparse, os, subprocess
import numpy as np
from nexusformat.nexus import nxload
from nexpy.gui.utils import natural_sort


def main():

    parser = argparse.ArgumentParser(
        description="Perform workflow for scan")
    parser.add_argument('-d', '--directory', default='', help='scan directory')
    parser.add_argument('-e', '--entries', default=['f1', 'f2', 'f3'], 
        nargs='+', help='names of entries to be processed')
                        
    
    args = parser.parse_args()

    directory = args.directory.rstrip('/')

    print("Processing directory '%s'" % directory)
    
    wrapper_files = sorted([os.path.join(directory, filename) 
                            for filename in os.listdir(directory) 
                            if filename.endswith('.nxs')], key=natural_sort)
    summary = []
    for wrapper_file in wrapper_files:
        print("Processing %s" % wrapper_file)
        root = nxload(wrapper_file)
        for e in args.entries:        
            print("Processing %s" % e)
            status = '%s[%s]:' % (wrapper_file, e)
            if e in root and 'data' in root[e] and 'instrument' in root[e]:
                if 'nxlink' in root[e] or 'logs' in root[e]['instrument']:
                    status = status + ' nxlink'
                if 'nxmax' in root[e] or 'maximum' in root[e]['data'].attrs:
                    status = status + ' nxmax'
                if 'nxfind' in root[e] or 'peaks' in root[e]:
                    status = status + ' nxfind'
                if 'nxcopy' in root[e]:
                    status = status + ' nxcopy'
                if ('nxrefine' in root[e] or 
                    ('detector' in root[e] and 
                     'orientation_matrix' in root[e]['instrument/detector'])):
                    status = status + ' nxrefine'
                if 'nxtransform' in root[e] or 'transform' in root[e]:
                    status = status + ' nxtransform'
            else:
                status = status + ' file incomplete'
            summary.append(status)            
            
    summary_file = os.path.join(directory, 'nxsummary.log')
    with open(summary_file, 'w') as f:
        f.write('\n'.join(summary))
    print("Results summarized in '%s'" % summary_file)  

if __name__=="__main__":
    main()
