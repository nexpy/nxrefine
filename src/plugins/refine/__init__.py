from PySide import QtGui
import merge_images, apply_mask, find_maximum, find_peaks, calculate_angles
import define_lattice, refine_lattice, refine_orientation, transform_data

def plugin_menu(parent):
    menu = QtGui.QMenu('Refine')
    menu.addAction(QtGui.QAction('Merge Images', parent, 
                   triggered=merge_images.show_dialog))
    menu.addAction(QtGui.QAction('Apply Mask', parent, 
                   triggered=apply_mask.show_dialog))
    menu.addAction(QtGui.QAction('Find Maximum', parent, 
                   triggered=find_maximum.show_dialog))
    menu.addAction(QtGui.QAction('Find Peaks', parent, 
                   triggered=find_peaks.show_dialog))
    menu.addAction(QtGui.QAction('Calculate Angles', parent, 
                   triggered=calculate_angles.show_dialog))
    menu.addAction(QtGui.QAction('Define Lattice', parent, 
                   triggered=define_lattice.show_dialog))
    menu.addAction(QtGui.QAction('Refine Lattice', parent, 
                   triggered=refine_lattice.show_dialog))
    menu.addAction(QtGui.QAction('Refine Orientation', parent, 
                   triggered=refine_orientation.show_dialog))
    menu.addAction(QtGui.QAction('Transform Data', parent, 
                   triggered=transform_data.show_dialog))
    return menu