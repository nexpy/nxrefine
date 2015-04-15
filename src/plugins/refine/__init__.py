from PySide import QtGui
import new_scan, stack_images, apply_mask, find_maximum, find_peaks
import calculate_angles, copy_parameters
import define_lattice, refine_lattice
import define_orientation, refine_orientation, transform_data

def plugin_menu(parent):
    menu = QtGui.QMenu('Refine')
    menu.addAction(QtGui.QAction('New Scan', parent, 
                   triggered=new_scan.show_dialog))
    menu.addAction(QtGui.QAction('Stack Images', parent, 
                   triggered=stack_images.show_dialog))
    menu.addAction(QtGui.QAction('Apply Mask', parent, 
                   triggered=apply_mask.show_dialog))
    menu.addAction(QtGui.QAction('Find Maximum', parent, 
                   triggered=find_maximum.show_dialog))
    menu.addAction(QtGui.QAction('Find Peaks', parent, 
                   triggered=find_peaks.show_dialog))
    menu.addAction(QtGui.QAction('Copy Parameters', parent, 
                   triggered=copy_parameters.show_dialog))
    menu.addAction(QtGui.QAction('Calculate Angles', parent, 
                   triggered=calculate_angles.show_dialog))
    menu.addAction(QtGui.QAction('Define Lattice', parent, 
                   triggered=define_lattice.show_dialog))
    menu.addAction(QtGui.QAction('Refine Lattice', parent, 
                   triggered=refine_lattice.show_dialog))
    menu.addAction(QtGui.QAction('Define Orientation', parent, 
                   triggered=define_orientation.show_dialog))
    menu.addAction(QtGui.QAction('Refine Orientation', parent, 
                   triggered=refine_orientation.show_dialog))
    menu.addAction(QtGui.QAction('Transform Data', parent, 
                   triggered=transform_data.show_dialog))
    return menu