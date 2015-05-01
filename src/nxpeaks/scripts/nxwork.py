import argparse, os, subprocess
import numpy as np

def crash(msg):
    print msg
    exit(1)

def main():

    parser = argparse.ArgumentParser(
        description="Perform workflow for scan")
    parser.add_argument('-s', '--sample', help='sample name')
    parser.add_argument('-l', '--label', help='sample label')
    parser.add_argument('-d', '--directory', default='', help='scan directory')
    parser.add_argument('-t', '--temperature', help='temperature of scan')
    parser.add_argument('-f', '--filenames', default=['f1', 'f2', 'f3'], 
        nargs='+', help='names of NeXus files to be linked to this file')
    parser.add_argument('-m', '--maskfiles', 
        default=['mask_f1', 'mask_f2', 'mask_f3'], nargs='+',
        help='name of the pixel mask files')
    parser.add_argument('-p', '--parent', help='file name of file to copy from')
    
    args = parser.parse_args()

    sample = args.sample
    label = args.label
    directory = args.directory.rstrip('/')
    if sample is None and label is None:
        sample = os.path.basename(os.path.dirname(os.path.dirname(directory)))   
        label = os.path.basename(os.path.dirname(directory))
        directory = os.path.basename(directory)

    print "Processing sample '%s', label '%s', scan '%s'\n" % (sample,
                                                               label,
                                                               directory)
    
    temperature = np.float32(args.temperature)
    files = args.filenames
    maskfiles = args.maskfiles
    if len(maskfiles) < len(files):
        if len(maskfiles) == 1:
            maskfiles = [maskfiles] * len(files)
        else:
            crash('No. of maskfiles must same as no. of filenames or 1')
    parent = args.parent

    label_path = '%s/%s' % (sample, label)
    wrapper_file = '%s/%s_%s.nxs' % (label_path, sample, directory)

    if sample == None:
        crash('Requires sample!')
    if not os.path.exists(label_path):
        crash("Label does not exist: "+label_path)
    
    if not os.path.exists(wrapper_file):
        print "\n\nSetting up %s\n" % wrapper_file
        subprocess.call('nxsetup -s %s -l %s -d %s -t %s -f %s'
                        % (sample, label, directory, temperature, 
                           ' '.join(files)), shell=True)

    for (f, m) in zip(files, maskfiles):
        path = '%s/%s/%s/%s' % (sample, label, directory, f)
        if not os.path.exists(path+'.nxs'):
            print "\n\nStacking %s.nxs\n" % path
            subprocess.call('nxstack -d %s -p scan -e cbf -o %s.nxs -s scan.spec -c None'
                            % (path, path), shell=True)
        print "\n\nLinking %s.nxs\n" % path
        subprocess.call('nxlink -s %s -l %s -d %s -f %s -m %s'
                        % (sample, label, directory, f, m), shell=True)
        print "\n\nDetermining maximum counts in %s.nxs\n" % path
        subprocess.call('nxmax -f %s -p %s/data'
                        % (wrapper_file, f), shell=True)
        print "\n\nFinding peaks in %s.nxs\n" % path
        subprocess.call('nxfind -f %s -p %s/data -s 500 -e 1000'
                        % (wrapper_file, f), shell=True)

    if parent:
        print "\n\nCopying parameters from %s\n" % parent
        subprocess.call('nxcopy -f %s -o %s' 
                        % (parent, wrapper_file), shell=True)

if __name__=="__main__":
    main()
