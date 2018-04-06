from __future__ import absolute_import

from . import new_experiment, load_calibration, calibrate_powder, new_scan
from . import create_mask, stack_images, find_maximum, find_peaks
from . import calculate_angles, copy_parameters
from . import define_lattice, refine_lattice
from . import define_orientation, transform_data

def plugin_menu():
    menu = 'Refine'
    actions = []
    actions.append(('New Experiment', new_experiment.show_dialog))
    actions.append(('Load Calibration', load_calibration.show_dialog))
    actions.append(('Calibrate Powder', calibrate_powder.show_dialog))
    actions.append(('Create Mask', create_mask.show_dialog))
    actions.append(('New Scan', new_scan.show_dialog))
    actions.append(('Stack Images', stack_images.show_dialog))
    actions.append(('Find Maximum', find_maximum.show_dialog))
    actions.append(('Find Peaks', find_peaks.show_dialog))
    actions.append(('Copy Parameters', copy_parameters.show_dialog))
    actions.append(('Calculate Angles', calculate_angles.show_dialog))
    actions.append(('Define Lattice', define_lattice.show_dialog))
    actions.append(('Define Orientation', define_orientation.show_dialog))
    actions.append(('Refine Lattice', refine_lattice.show_dialog))
    actions.append(('Transform Data', transform_data.show_dialog))
    return menu, actions