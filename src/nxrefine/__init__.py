# -----------------------------------------------------------------------------
# Copyright (c) 2013-2021, NeXpy Development Team.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file COPYING, distributed with this software.
# -----------------------------------------------------------------------------

__package_name__ = 'NXrefine'
from ._version import get_versions
__version__ = get_versions()['version']
del get_versions

__documentation_author__ = 'Ray Osborn'
__documentation_copyright__ = '2013-21, Ray Osborn'

__license__ = 'BSD'
__author_name__ = 'Ray Osborn'
__author_email__ = 'rosborn@anl.gov'
__author__ = __author_name__ + ' <' + __author_email__ + '>'

__description__ = 'NXrefine: Python package to process crystallographic data'
__long_description__ = ("""NXRefine implements a complete workflow for the
reduction of single-crystal x-ray scattering measured on an area detector as a
series of frames collected while rotating a sample continuously in a
monochromatic beam.
""")
