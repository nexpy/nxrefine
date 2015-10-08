import argparse, os, subprocess, time


def crash(msg):
    print msg
    exit(1)


def main():

    parser = argparse.ArgumentParser(
        description="Setup a list of SPEC macros for set of scans")
    parser.add_argument('-r', '--root', default='rosenkranz-311-1', 
                        help='root directory')
    parser.add_argument('-s', '--sample', help='sample name')
    parser.add_argument('-l', '--label', default='', help='sample label')
    parser_group = parser.add_mutually_exclusive_group()
    parser_group.add_argument('-d', '--directory', help='scan directory')
    parser_group.add_argument('-t', '--temperatures', nargs='+', help='list of temperatures')
    parser.add_argument('-f', '--filenames', default=['f1', 'f2', 'f3'], 
        nargs='+', help='names of NeXus files to be linked to this file')
    parser.add_argument('-m', '--maskfiles', 
        default=['mask_f1', 'mask_f2', 'mask_f3'], nargs='+',
        help='name of the pixel mask files')
    parser.add_argument('-x', '--x_motors', default=[0.0, 5.0, 10.0], nargs='+',
        help='x-motor positions')
    parser.add_argument('-y', '--y_motors', default=[0.0, 5.0, 10.0], nargs='+',
        help='y-motor positions')
    parser.add_argument('-p', '--parent', help='file name of file to copy from')
    parser.add_argument('-o', '--output', default='scans.mac', help='name of SPEC macro')
    args = parser.parse_args()

    root = args.root
    sample = args.sample
    label = args.label
    directory = args.directory
    files = args.filenames
    maskfiles = args.maskfiles
    if len(maskfiles) < len(files):
        if len(maskfiles) == 1:
            maskfiles = [maskfiles] * len(files)
        else:
            crash('No. of maskfiles must same as no. of filenames or 1')
    x_motors = args.x_motors
    y_motors = args.y_motors    
    temperatures = args.temperatures
    parent = args.parent
    spec_macro = args.output
    
    spec_file = open(spec_macro, 'w')
    spec_commands = []

    if directory is not None:
        pars = '-s %s -l %s -d %s -f %s -m %s' % (
               sample, label, directory, ' '.join(files), ' '.join(maskfiles))
        if parent:
            pars = pars + ' -p %s' % parent
        subprocess.call('nxsetup %s' % pars, shell=True)
        for (f, m, x, y) in zip(files, maskfiles, x_motors, y_motors):
            pilatus_dir = os.path.join('/ramdisk', root, sample, label, directory, f, '')
            spec_dir = os.path.join(sample, label, directory, f, '')
            spec_commands.append('pilatus_scan %s %s %s %s'  
                                 % (pilatus_dir, spec_dir, x, y))    
    else:
        for temperature in temperatures:
            dir = temperature+'K'
            pars = '-s %s -l %s -d %s -t %s -f %s -m %s' % (
                   sample, label, dir, temperature, 
                   ' '.join(files), ' '.join(maskfiles))
            if parent:
                pars = pars + ' -p %s' % parent
            subprocess.call('nxsetup %s' % pars, shell=True)
            for (f, m, x, y) in zip(files, maskfiles, x_motors, y_motors):
                pilatus_dir = os.path.join('/ramdisk', root, sample, label, dir, f, '')
                spec_dir = os.path.join(sample, label, dir, f, '')
                spec_commands.append('pilatus_scan %s %s %s %s %s'  
                                     % (pilatus_dir, spec_dir, x, y, temperature))

    spec_file.write('\n'.join(spec_commands))
    spec_file.close()

if __name__=="__main__":
    main()
