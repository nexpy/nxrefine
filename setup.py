#!/usr/bin/env python
#-----------------------------------------------------------------------------
# Copyright (c) 2013, nxpeaks Development Team.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file COPYING, distributed with this software.
#-----------------------------------------------------------------------------

#from distutils.core import setup, Extension
from setuptools import setup, find_packages, Extension

import numpy
import os, sys

sys.path.insert(0, os.path.join('src', ))
import nxpeaks

verbose=1

setup (name = nxpeaks.__package_name__, 
       version = nxpeaks.__version__,
       license = nxpeaks.__license__,
       description = nxpeaks.__description__,
       long_description = nxpeaks.__long_description__,
       author=nxpeaks.__author_name__,
       author_email=nxpeaks.__author_email__,
       platforms='any',
       requires = ('numpy', 'scipy'),
       package_dir = {'': 'src'},
       packages = find_packages('src'),
       ext_modules=[Extension('nxpeaks.connectedpixels', 
                        ['src/nxpeaks/connectedpixels.c','src/nxpeaks/blobs.c'],
                        depends=['src/nxpeaks/blobs.h'],
                        include_dirs=[numpy.get_include()]),
                    Extension("nxpeaks.closest", 
                        ['src/nxpeaks/closest.c'], 
                        include_dirs=[numpy.get_include()])],
       entry_points={
            # create & install scripts in <python>/bin
            'console_scripts': ['nxsetup=nxpeaks.scripts.nxsetup:main',
                                'nxcopy=nxpeaks.scripts.nxcopy:main',
                                'nxlink=nxpeaks.scripts.nxlink:main',
                                'nxfind=nxpeaks.scripts.nxfind:main',
                                'nxmake=nxpeaks.scripts.nxmake:main',
                                'nxmask=nxpeaks.scripts.nxmask:main',
                                'nxmax=nxpeaks.scripts.nxmax:main',
                                'nxorient=nxpeaks.scripts.nxorient:main',
                                'nxwork=nxpeaks.scripts.nxwork:main',
                                'nxrun=nxpeaks.scripts.nxrun:main',
                                'nxscan=nxpeaks.scripts.nxscan:main',
                                'nxcombine=nxpeaks.scripts.nxcombine:main',
                                'nxtransform=nxpeaks.scripts.nxtransform:main'],
       },
#       data_files=[('', ['bm/b1.gif', 'bm/b2.gif']),
#                  ('config', ['cfg/data.cfg']),
#                  ('/etc/init.d', ['init-script'])],
       classifiers= ['Development Status :: 4 - Beta',
                     'Intended Audience :: Science/Research',
                     'License :: OSI Approved :: BSD License',
                     'Programming Language :: Python',
                     'Programming Language :: Python :: 2',
                     'Programming Language :: Python :: 2.7',
                     'Topic :: Scientific/Engineering']
      )

