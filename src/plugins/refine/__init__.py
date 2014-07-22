from PySide import QtGui
import find_maximum, find_peaks, calculate_angles, define_lattice, refine_lattice

def plugin_menu(parent):
    menu = QtGui.QMenu('Refine')
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
    return menu