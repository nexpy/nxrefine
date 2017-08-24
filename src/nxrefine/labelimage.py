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


from nxrefine import blobcorrector, connectedpixels
# Names of property columns in array
from nxrefine.connectedpixels import s_1, s_I, s_I2,\
    s_fI, s_ffI, s_sI, s_ssI, s_sfI, s_oI, s_ooI, s_foI, s_soI, \
    bb_mn_f, bb_mn_s, bb_mx_f, bb_mx_s, bb_mn_o, bb_mx_o, \
    mx_I, mx_I_f, mx_I_s, mx_I_o, dety, detz, \
    avg_i, f_raw, s_raw, o_raw, f_cen, s_cen, \
    m_ss, m_ff, m_oo, m_sf, m_so, m_fo

from math import sqrt

import sys

import numpy as np


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

    def __init__(self,
                 shape,
                 spatial = blobcorrector.perfect(),
                 flipper = flip2):
        """
        Shape - image dimensions
        spatial - correction of of peak positions
        """
        self.shape = shape  # Array shape
        self.corrector = spatial  # applies spatial distortion
        self.fs2yz = flipper # generates y/z

        self.onfirst = 1    # Flag for first image in series
        self.onlast = 0     # Flag for last image in series
        self.blim = np.zeros(shape, np.int32)  # 'current' blob image 
        self.npk = 0        #  Number of peaks on current
        self.res = None     #  properties of current
        
        self.threshold = None # cache for writing files

        self.lastbl = np.zeros(shape, np.int32)# 'previous' blob image
        self.lastres = None
        self.lastnp = "FIRST" # Flags initial state

        self.verbose = 0    # For debugging

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

    def mergelast(self):
        """
        Merge the last two images searches
        """
        if self.lastnp == "FIRST":
            # No previous image available, this was the first
            # Swap the blob images
            self.lastbl, self.blim = self.blim, self.lastbl
            self.lastnp = self.npk
            self.lastres = self.res
            return            
        if self.npk > 0 and self.lastnp > 0:
            # Thanks to Stine West for finding a bug here
            # 
            self.npk = connectedpixels.bloboverlaps(self.lastbl,
                                                    self.lastnp,
                                                    self.lastres,
                                                    self.blim,
                                                    self.npk,
                                                    self.res,
                                                    self.verbose)
        if self.lastnp > 0:
            # Fill out the moments of the "closed" peaks
            # print "calling blobmoments with",self.lastres
            ret = connectedpixels.blob_moments(self.lastres[:self.lastnp])
        # lastres is now moved forward into res
        self.lastnp = self.npk   # This is array dim
        if self.npk > 0:
            self.lastres = self.res[:self.npk]  # free old lastres I hope
        else:
            self.lastres = None
        # Also swap the blob images
        self.lastbl, self.blim = self.blim, self.lastbl

    def output2dpeaks(self):
        """
        Write something compatible with the old ImageD11 format
        which fabian is reading.
        This is called before mergelast, so we write self.npk/self.res
        """
        
        ret = connectedpixels.blob_moments(self.res)

        for i in self.res[:self.npk]:
            if i[s_1] < 0.1:
                raise Exception("Empty peak on current frame")
            i[s_cen], i[f_cen] = self.corrector.correct(i[s_raw], i[f_raw])
            
    def finalise(self):
        """
        Write out the last frame
        """
        self.onlast = 1
        if self.lastres is not None:
            ret = connectedpixels.blob_moments(self.lastres)



