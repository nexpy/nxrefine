# -----------------------------------------------------------------------------
# Copyright (c) 2022, Argonne National Laboratory.
#
# Distributed under the terms of an Open Source License.
#
# The full license is in the file LICENSE.pdf, distributed with this software.
# -----------------------------------------------------------------------------

from . import (calibrate_powder, create_mask, edit_settings, import_scans,
               make_scans, new_configuration, new_experiment, new_sample,
               new_scan, sum_scans)


def plugin_menu():
    menu = 'Experiment'
    actions = []
    actions.append(('New Experiment', new_experiment.show_dialog))
    actions.append(('New Configuration', new_configuration.show_dialog))
    actions.append(('Calibrate Powder', calibrate_powder.show_dialog))
    actions.append(('Create Mask', create_mask.show_dialog))
    actions.append(('New Sample', new_sample.show_dialog))
    actions.append(('New Scan', new_scan.show_dialog))
    actions.append(('Make Scans', make_scans.show_dialog))
    actions.append(('Import Scans', import_scans.show_dialog))
    actions.append(('Sum Scans', sum_scans.show_dialog))
    actions.append(('Edit Settings', edit_settings.show_dialog))
    return menu, actions
