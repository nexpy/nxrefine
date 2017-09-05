#-----------------------------------------------------------------------------
# Copyright (c) 2013, NeXpy Development Team.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file COPYING, distributed with this software.
#-----------------------------------------------------------------------------
from __future__ import absolute_import

__package_name__ = u'NXrefine'
from ._version import get_versions
__version__ = get_versions()['version']
del get_versions

__documentation_author__ = u'Ray Osborn'
__documentation_copyright__ = u'2013-17, Ray Osborn'

__license__ = u'BSD'
__author_name__ = u'NeXpy Development Team'
__author_email__ = u'nexpydev@gmail.com'
__author__ = __author_name__ + u' <' + __author_email__ + u'>'

__description__ = u'NXrefine: Python package to process crystallographic data'
__long_description__ = \
u"""
This is designed to be used in coordination with NeXpy. It utilizes software
developed by Jon Wright as part of the ImageD11 package to search for Bragg
peaks within multiple images. It has been adapted to work on three-dimensional
NeXus files, rather than multiple TIFF files.
"""
