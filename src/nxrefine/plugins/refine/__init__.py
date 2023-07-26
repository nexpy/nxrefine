# -----------------------------------------------------------------------------
# Copyright (c) 2013-2023, AXMAS Development Team.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file COPYING, distributed with this software.
# -----------------------------------------------------------------------------

from . import (calculate_angles, calibrate_powder, choose_parameters,
               copy_parameters, create_mask, define_lattice, edit_settings,
               find_maximum, find_peaks, import_scans, make_scans,
               new_configuration, new_experiment, new_sample, new_scan,
               prepare_mask, refine_lattice, sum_scans, transform_data)


def plugin_menu():
    menu = 'Refine'
    actions = []
    actions.append(('New Experiment', new_experiment.show_dialog))
    actions.append(('New Configuration', new_configuration.show_dialog))
    actions.append(('Choose Parameters', choose_parameters.show_dialog))
    actions.append(('Calibrate Powder', calibrate_powder.show_dialog))
    actions.append(('Create Mask', create_mask.show_dialog))
    actions.append(('New Sample', new_sample.show_dialog))
    actions.append(('New Scan', new_scan.show_dialog))
    actions.append(('Make Scans', make_scans.show_dialog))
    actions.append(('Import Scans', import_scans.show_dialog))
    actions.append(('Sum Scans', sum_scans.show_dialog))
    actions.append(('Find Maximum', find_maximum.show_dialog))
    actions.append(('Find Peaks', find_peaks.show_dialog))
    actions.append(('Prepare 3D Mask', prepare_mask.show_dialog))
    actions.append(('Copy Parameters', copy_parameters.show_dialog))
    actions.append(('Calculate Angles', calculate_angles.show_dialog))
    actions.append(('Define Lattice', define_lattice.show_dialog))
    actions.append(('Refine Lattice', refine_lattice.show_dialog))
    actions.append(('Transform Data', transform_data.show_dialog))
    actions.append(('Edit Settings', edit_settings.show_dialog))
    return menu, actions
