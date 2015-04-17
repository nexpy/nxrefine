import argparse, os, subprocess
import numpy as np

def main():

    parser = argparse.ArgumentParser(
        description="Perform workflow for scan")
    parser.add_argument('-s', '--sample', help='sample name')
    parser.add_argument('-l', '--label', default='', help='sample label')
    parser.add_argument('-d', '--directory', default='', help='scan directory')
    parser.add_argument('-t', '--temperature', help='temperature of scan')
    parser.add_argument('-f', '--filenames', default=['f1', 'f2', 'f3'], 
        nargs='+', help='names of NeXus files to be linked to this file')
    parser.add_argument('-m', '--maskfile', default='pilatus_mask.nxs',
        help='name of the pixel mask file')
    parser.add_argument('-p', '--parent', help='file name of file to copy from')
    
    args = parser.parse_args()

    sample = args.sample
    label = args.label
    directory = args.directory
    temperature = np.float32(args.temperature)
    files = args.filenames
    if args.maskfile is not None:
        mask = nxload(args.maskfile)['entry/mask']
    else:
        mask = None
    parent = args.parent

    label_path = '%s/%s' % (sample, label)
    wrapper_file = '%s/%s_%s.nxs' % (label_path, sample, directory)

    if not os.path.exists(wrapper_file):
        setup_command = 'nxsetup -s %s -l %s -d %s -t %s -f %s' \
                        % (sample, label, directory, temperature, ' '.join(files))

    for f in files:
        path = '%s/%s/%s/%s' % (sample, label, directory, f)
        subprocess.call('nxstack -d %s -p scan -e cbf -o %s.nxs -c None'
                        % (path, path))
        subprocess.call('nxlink -s %s -l %s -d %s -f %s -m pilatus_mask.nxs'
                        % (sample, label, directory, f))
        subprocess.call('nxmax -d %s -f %s -p %s/data'
                        % (label_path, wrapper_file, f))
        subprocess.call('nxfind -d %s -f %s -p %s/data -s 500 -e 1000'
                        % (label_path, wrapper_file, f))

    if parent:
        subprocess.call('nxcopy -f %s/%s -o %s' 
                        % (label_path, parent, wrapper_file))

if __name__=="__main__":
    main()
