import argparse, os, subprocess
import numpy as np
from nexusformat.nexus import nxload
from nexpy.gui.utils import natural_sort


def main():

    parser = argparse.ArgumentParser(
        description="Perform workflow for scan")
    parser.add_argument('-d', '--directory', default='', help='scan directory')
                        
    
    args = parser.parse_args()

    directory = args.directory.rstrip('/')

    print("Processing directory '%s'" % directory)
    
    wrapper_files = sorted([os.path.join(directory, filename) 
                            for filename in directory 
                            if filename.endswith('.nxs')], key=natural_sort)

    summary = []
    for wrapper_file in wrapper_files:
        print("Processing %s" % wrapper_file)
        root = nxload(wrapper_file)
        scan_label = os.path.splitext(os.path.basename(wrapper_file))[0][len(sample)+1:]
        for e in entries:        
            print("Processing %s" % e)
            status = '%s[%s]:' % (wrapper_file, e)
            if 'nxlink' in root[e] or logs in root[e]['instrument']:
                status = status + ' nxlink'
            if 'nxmax' in root[e] or 'maximum' in root[e]['data'].attrs:
                status = status + ' nxmax'
            if 'nxfind' in root[e] or 'peaks' in root[e]:
                status = status + ' nxfind'
            if 'nxcopy' in root[e]:
                status = status + ' nxcopy'
            if 'nxrefine' in root[e] or 'orientation_matrix' in root[e]['instrument/detector']:
                status = status + ' nxrefine'
            if 'nxtransform' in root[e] or 'transform' in root[e]:
                status = status + ' nxtransform'
            summary.append(status)            
            
    summary_file = os.path.join(directory, 'nxsummary.log')
    with open(summary_file, 'w') as f:
        f.write('\n'.join(summary))
    print("Results summarized in '%s'" % summary_file)  

if __name__=="__main__":
    main()
