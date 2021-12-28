#!/usr/bin/env python
# -----------------------------------------------------------------------------
# Copyright (c) 2014-2021, NeXpy Development Team.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file COPYING, distributed with this software.
# -----------------------------------------------------------------------------
import os

import numpy
from setuptools import Extension, setup

setup(ext_modules=[Extension('nxrefine.connectedpixels',
                             ['src/nxrefine/connectedpixels.c',
                              'src/nxrefine/blobs.c'],
                             depends=['src/nxrefine/blobs.h'],
                             include_dirs=[numpy.get_include()]),
                   Extension("nxrefine.closest",
                             ['src/nxrefine/closest.c'],
                             include_dirs=[numpy.get_include()])]
      )
