# -----------------------------------------------------------------------------
# Copyright (c) 2013-2023, AXMAS Development Team.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file COPYING, distributed with this software.
# -----------------------------------------------------------------------------

from . import (calculate_angles, choose_parameters, copy_parameters,
               define_lattice, find_maximum, find_peaks, prepare_mask,
               refine_lattice, transform_data)


def plugin_menu():
    menu = 'Refine'
    actions = []
    actions.append(('Choose Parameters', choose_parameters.show_dialog))
    actions.append(('Copy Parameters', copy_parameters.show_dialog))
    actions.append(('Find Maximum', find_maximum.show_dialog))
    actions.append(('Find Peaks', find_peaks.show_dialog))
    actions.append(('Prepare 3D Mask', prepare_mask.show_dialog))
    actions.append(('Calculate Angles', calculate_angles.show_dialog))
    actions.append(('Define Lattice', define_lattice.show_dialog))
    actions.append(('Refine Lattice', refine_lattice.show_dialog))
    actions.append(('Transform Data', transform_data.show_dialog))
    return menu, actions
