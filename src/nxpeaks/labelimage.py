"""
Class to wrap the connectedpixels c extensions for labelling
blobs in images.
"""
# ImageD11_v1.0 Software for beamline ID11
# Copyright (C) 2005-2007  Jon Wright
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  0211-1307  USA


from nxpeaks import blobcorrector, connectedpixels
# Names of property columns in array
from nxpeaks.connectedpixels import s_1, s_I, s_I2,\
    s_fI, s_ffI, s_sI, s_ssI, s_sfI, s_oI, s_ooI, s_foI, s_soI, \
    bb_mn_f, bb_mn_s, bb_mx_f, bb_mx_s, bb_mn_o, bb_mx_o, \
    mx_I, mx_I_f, mx_I_s, mx_I_o, dety, detz, \
    avg_i, f_raw, s_raw, o_raw, f_cen, s_cen, \
    m_ss, m_ff, m_oo, m_sf, m_so, m_fo

from math import sqrt

import sys

import numpy.oldnumeric as n


# These should match the definitions in 
# /sware/exp/saxs/doc/SaxsKeywords.pdf
def flip1(x, y): 
    """ fast, slow to dety, detz"""
    return  x,  y
def flip2(x, y): 
    """ fast, slow to dety, detz"""
    return -x,  y   
def flip3(x, y): 
    """ fast, slow to dety, detz"""
    return  x, -y
def flip4(x, y): 
    """ fast, slow to dety, detz"""
    return -x, -y
def flip5(x, y): 
    """ fast, slow to dety, detz"""
    return  y,  x
def flip6(x, y): 
    """ fast, slow to dety, detz"""
    return  y, -x
def flip7(x, y): 
    """ fast, slow to dety, detz"""
    return -y,  x
def flip8(x, y): 
    """ fast, slow to dety, detz"""
    return -y, -x





class labelimage:
    """
    For labelling spots in diffraction images
    """

    titles = "#  sc  fc  omega" 
    format = "  %.4f"*3
    titles += "  Number_of_pixels"
    format += "  %.0f"
    titles += "  avg_intensity  s_raw  f_raw  sigs  sigf  covsf"
    format += "  %.4f"*6
    titles += "  sigo  covso  covfo"
    format += "  %.4f"*3
    titles += "  sum_intensity  sum_intensity^2"
    format += "  %.4f  %.4f"
    titles += "  IMax_int  IMax_s  IMax_f  IMax_o"
    format += "  %.4f  %.0f  %.0f  %.4f"
    titles += "  Min_s  Max_s  Min_f  Max_f  Min_o  Max_o"
    format += "  %.0f"*4 + "  %.4f"*2
    titles += "  dety  detz"
    format += "  %.4f"*2
    titles += "  onfirst  onlast  spot3d_id"
    format += "  %d  %d  %d"
    titles += "\n"
    format += "\n"


    def __init__(self,
                 shape,
                 fileout = sys.stdout,
                 spatial = blobcorrector.perfect(),
                 flipper = flip2,
                 sptfile = sys.stdout ):
        """
        Shape - image dimensions
        fileout - writeable stream for merged peaks
        spatial - correction of of peak positions
        """
        self.shape = shape  # Array shape
        if not hasattr(sptfile,"write"):
            self.sptfile = open(sptfile, "w")
        else:
            self.sptfile = sptfile # place for peaksearch to print - file object
        self.corrector = spatial  # applies spatial distortion
        self.fs2yz = flipper # generates y/z

        self.onfirst = 1    # Flag for first image in series
        self.onlast = 0     # Flag for last image in series
        self.blim = n.zeros(shape, n.Int)  # 'current' blob image 
        self.npk = 0        #  Number of peaks on current
        self.res = None     #  properties of current
        
        self.threshold = None # cache for writing files

        self.lastbl = n.zeros(shape, n.Int)# 'previous' blob image
        self.lastres = None
        self.lastnp = "FIRST" # Flags initial state

        self.verbose = 0    # For debugging

        if hasattr(fileout,"write"):
            self.outfile = fileout
        else:
            self.outfile = open(fileout,"w")

        self.spot3d_id = 0 # counter for printing
        try:
            self.outfile.write(self.titles)
        except:
            print type(self.outfile),self.outfile
            raise

    def peaksearch(self, data, threshold, omega):
        """
        # Call the c extensions to do the peaksearch, on entry:
        #
        # data = 2D Numeric array (of your data)
        # threshold = float - pixels above this number are put into objects
        """
        self.threshold = threshold
        self.npk = connectedpixels.connectedpixels(data, 
                                                  self.blim, 
                                                  threshold,
                                                  self.verbose)
        if self.npk > 0:
            self.res = connectedpixels.blobproperties(data, 
                                                      self.blim, 
                                                      self.npk,
                                                      omega=omega)
        else:
            # What to do?
            self.res = None

    def output2dpeaks(self, file_obj):
        """
        Write something compatible with the old ImageD11 format
        which fabian is reading.
        This is called before mergelast, so we write self.npk/self.res
        """
        
        file_obj.write("# Threshold level %f\n"%( self.threshold))
        file_obj.write("# Number_of_pixels Average_counts    s   f     sc   fc      sig_s  sig_f  cov_sf  IMax_int\n")
        ret = connectedpixels.blob_moments(self.res)

        fs = "%d  "+ "%f  "*9 + "\n"
        for i in self.res[:self.npk]:
            if i[s_1] < 0.1:
                raise Exception("Empty peak on current frame")
            i[s_cen], i[f_cen] = self.corrector.correct(i[s_raw], i[f_raw])
            file_obj.write(fs % (i[s_1],  i[avg_i], i[s_raw], i[f_raw],
                                 i[s_cen], i[f_cen],
                                 i[m_ss], i[m_ff], i[m_sf], i[mx_I]))
        file_obj.write("\n")
