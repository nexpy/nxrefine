"""
Script for peaksearching images from the command line

Uses the connectedpixels extension for finding blobs above a threshold
and the blobcorrector(+splines) for correcting them for spatial distortion

Defines one function (peaksearch) which might be reused
"""

from math import sqrt
import argparse, glob, os, sys, time

import numpy as np

from nexusformat.nexus import nxload

from nxpeaks import blobcorrector
from nxpeaks.labelimage import labelimage
from nxpeaks.peakmerge import peakmerger

class timer:
    def __init__(self):
        self.start = time.time()
        self.now = self.start
        self.msgs = []
    def msg(self,msg):
        self.msgs.append(msg)
    def tick(self,msg=""):
        now = time.time()
        self.msgs.append("%s %.2f/s"%(msg,now-self.now))
        self.now = now
    def tock(self,msg=""):
        self.tick(msg)
        print " ".join(self.msgs),"%.2f/s"% (self.now-self.start)
        sys.stdout.flush()

def peaksearch(filename, data, corrfunc, threshold, lio):
    """
    filename  : The name of the NeXus file for progress info 	
    data : NXdata containing data and rotation angles
    thresholds : [ float[1], float[2] etc]
    lio : label image object
    """
    t = timer()
    picture = data.v.nxdata.astype(np.float32)

    f = lio.sptfile
    f.write("\n\n# File %s\n" % (filename))
    f.write("# Processed on %s\n" % (time.asctime()))
    try:
        f.write("# Spatial correction from %s\n" % (corrector.splinefile))
        f.write("# SPLINE X-PIXEL-SIZE %s\n" % (str(corrector.xsize)))
        f.write("# SPLINE Y-PIXEL-SIZE %s\n" % (str(corrector.ysize)))
    except:
        pass
    try:
        f.write("# Title = %s\n" % data.title)
    except KeyError:
        pass

    # Get the rotation angle for this image
    omega = data.rotation_angle.nxdata

    t.tick(filename)
    f = lio.sptfile
    f.write("# Omega = %f\n"%(omega))
    lio.peaksearch(picture, threshold, omega)
    f.write("# Threshold = %f\n"%(threshold))
    f.write("# npks = %d\n"%(lio.npk))
    #
    if lio.npk > 0:
        lio.output2dpeaks(f)
    t.msg("omega=%s T=%-5d n=%-5d;" % (omega, int(threshold), lio.npk)) 
    # Close the output file
    # Finish progress indicator for this file
    t.tock()
    sys.stdout.flush()
    return None 


def findpeaks(options, args):
    """
    To be called with options from command line
    """
    ################## debugging still
    for a in args:
        print "arg: "+str(a)+","+str(type(a))
    ###################
    print "This peaksearcher is from",__file__

    if len(args) == 0  and options.filename is None:
        raise ValueError("No files to process")
    else:
        directory = options.directory
        filename = options.filename
        outfile = os.path.splitext(os.path.basename(filename))[0]
        if not directory:
            directory = os.getcwd()
        nexus_file = nxload(os.path.join(directory, filename))
        rotation_angle = nexus_file.entry.data.rotation_angle.nxdata    

    if options.threshold is None:
        if 'maximum' in nexus_file.entry.data.v.attrs:
            threshold = int(nexus_file.entry.data.v.maximum / 20)
        else:
            raise ValueError("No threshold supplied [-t 1234]")
    else:
        threshold = np.float32(options.threshold)

    print "Avoiding spatial correction"
    corrfunc = blobcorrector.perfect()

    s = nexus_file.entry.data.v[0].shape # data array shape
    
    # Create label images
    mergefile=os.path.join(directory,"%s.flt" % outfile)
    spotfile = os.path.join(directory, "%s.spt" % outfile)
    li_obj = labelimage(shape = s, 
                        spatial = corrfunc,
                        sptfile = spotfile)

    start = time.time()
    print "File being treated in -> out, elapsed time"
    
    for i in range(rotation_angle.size):
        data = nexus_file.entry.data[i]
        omega = rotation_angle[i]
        t = timer()
        t.tick("Omega: "+str(omega)+" io/cor")
        peaksearch(filename, data, corrfunc, threshold, li_obj)

    li_obj.sptfile.close()

    merger = peakmerger()
    merger.readpeaks(spotfile)
    merger.harvestpeaks()
    merger.mergepeaks()
    merger.filter()
    merger.savepeaks(os.path.join(directory, '%s.flt' % outfile))

def get_options(parser):
        """ Add our options to a parser object """
        parser.add_option("-d", "--directory", action="store",
            dest="directory", type="string", default=None,
            help="Directory of the NeXus file" )
        parser.add_option("-f", "--file", action="store",
            dest="filename", type="string", default=None,
            help="Name of the NeXus file" )
        parser.add_option("-t", "--threshold", action="append", type="float",
             dest="threshold", default=None,
             help="Threshold level")
        return parser

def get_help(usage = True):
    """ return the help string for online help """
    import optparse, StringIO
    if usage:
        o = get_options(optparse.OptionParser())
    else:
        o = get_options(optparse.OptionParser(optparse.SUPPRESS_USAGE))
    f = StringIO.StringIO()
    o.print_help(f)
    return f.getvalue()

def main():
    myparser = None
    try:
        from optparse import OptionParser
        parser = OptionParser()
        myparser = get_options(parser)
        options, args = myparser.parse_args()
        findpeaks(options, args)
    except:
        if myparser != None:
            myparser.print_help()
        print "\n\n And here is the problem:\n"
        raise

if __name__=="__main__":
    main()
