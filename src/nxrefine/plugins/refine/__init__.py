from __future__ import absolute_import

from . import new_experiment, new_configuration, choose_parameters
from . import calibrate_powder, create_mask
from . import new_sample, new_scan, make_scans, sum_scans
from . import find_maximum, find_peaks, calculate_mask
from . import calculate_angles, copy_parameters
from . import define_lattice, refine_lattice
from . import transform_data
from . import manage_servers, manage_workflows

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
    actions.append(('Sum Scans', sum_scans.show_dialog))
    actions.append(('Find Maximum', find_maximum.show_dialog))
    actions.append(('Find Peaks', find_peaks.show_dialog))
    actions.append(('Calculate 3D Mask', calculate_mask.show_dialog))
    actions.append(('Copy Parameters', copy_parameters.show_dialog))
    actions.append(('Calculate Angles', calculate_angles.show_dialog))
    actions.append(('Define Lattice', define_lattice.show_dialog))
    actions.append(('Refine Lattice', refine_lattice.show_dialog))
    actions.append(('Transform Data', transform_data.show_dialog))
    actions.append(('Manage Workflows', manage_workflows.show_dialog))
    actions.append(('Manage Servers', manage_servers.show_dialog))
    return menu, actions