import os

from nexusformat.nexus import *
from nexpy.gui.pyqt import QtCore, QtWidgets
from nexpy.gui.datadialogs import BaseDialog, GridParameters
from nexpy.gui.utils import report_error, natural_sort

from nxrefine.nxreduce import Lock, NXReduce


def show_dialog():
    dialog = WorkflowDialog()
    dialog.show()
#    except NeXusError as error:
#        report_error("Defining New Experiment", error)


class WorkflowDialog(BaseDialog):

    def __init__(self, parent=None):
        super(WorkflowDialog, self).__init__(parent)

        self.set_layout(self.directorybox('Choose Sample Directory'),
                        self.filebox('Choose Parent File'),
                        self.action_buttons(('Update Status', self.update),
                                            ('Add to Queue', self.add_tasks)),
                        self.close_buttons(close=True))
        self.set_title('Manage Workflows')
        self.grid = None
        self.sample_directory = None

    def choose_directory(self):
        super(WorkflowDialog, self).choose_directory()
        self.sample_directory = self.get_directory()
        self.sample = os.path.basename(os.path.dirname(self.sample_directory))
        parent_file = os.path.join(self.sample_directory, 
                                   self.sample+'_parent.nxs')
        if os.path.exists(parent_file):
            self.filename.setText(os.path.basename(os.path.realpath(parent_file)))
        else:
            self.filename.setText('')
        self.root_directory = os.path.dirname(os.path.dirname(self.sample_directory))
        self.mainwindow.default_directory = self.sample_directory
        if self.grid:
            self.delete_grid(self.grid)
            self.grid = None

    def choose_file(self):
        super(WorkflowDialog, self).choose_file()
        self.make_parent()

    def make_parent(self):
        _parent = self.get_filename()
        _base = os.path.basename(os.path.splitext(_parent)[0])
        _scan = _base.replace(self.sample+'_', '')
        reduce = NXReduce(directory=os.path.join(self.sample_directory, _scan), 
                          overwrite=True)
        reduce.make_parent()
        if _parent:
            return _parent
        else:
            return None

    def is_parent(self, wrapper_file):
        parent_file = os.path.join(self.sample_directory, 
                                   self.sample+'_parent.nxs')
        if os.path.exists(parent_file):
            return wrapper_file == os.path.realpath(parent_file)
        else:
            return False

    def update(self):
        grid = QtWidgets.QGridLayout()
        grid.setSpacing(1)
        row = 0
        columns = ['Scan', 'nxlink', 'nxmax', 'nxfind', 'nxcopy', 'nxrefine', 
                   'nxtransform', 'nxcombine', 'overwrite', 'reduce']
        header = {}
        for col, column in enumerate(columns):
            header[column] = QtWidgets.QLabel(column)
            header[column].setFont(self.bold_font)
            header[column].setAlignment(QtCore.Qt.AlignHCenter)
            grid.addWidget(header[column], row, col)
        wrapper_files = sorted([os.path.join(self.sample_directory, filename) 
                            for filename in os.listdir(self.sample_directory) 
                            if filename.endswith('.nxs')], key=natural_sort)
        self.scans = {}
        for wrapper_file in wrapper_files:
            row += 1
            base_name = os.path.basename(os.path.splitext(wrapper_file)[0])
            scan_label = base_name.replace(self.sample+'_', '')
            if scan_label == 'parent':
                break
            directory = os.path.join(self.sample_directory, scan_label)
            status = {}
            with Lock(wrapper_file):
                root = nxload(wrapper_file)
            grid.addWidget(QtWidgets.QLabel(scan_label), row, 0, QtCore.Qt.AlignHCenter)
            status['nxlink'] = self.new_checkbox()
            status['nxmax'] = self.new_checkbox()
            status['nxfind'] = self.new_checkbox()
            status['nxcopy'] = self.new_checkbox()
            status['nxrefine'] = self.new_checkbox()
            status['nxtransform'] = self.new_checkbox()
            status['nxcombine'] = self.new_checkbox()
            status['overwrite'] = self.new_checkbox() 
            status['reduce'] = self.new_checkbox() 
            for i,e in enumerate([entry for entry in root.entries if entry != 'entry']):
                if e in root and 'data' in root[e] and 'instrument' in root[e]:
                    self.update_checkbox(status['nxlink'], i,
                        'nxlink' in root[e] or 'logs' in root[e]['instrument'])
                    self.update_checkbox(status['nxmax'], i,
                        'nxmax' in root[e] or 'maximum' in root[e]['data'].attrs)
                    self.update_checkbox(status['nxfind'], i,
                        'nxfind' in root[e] or 'peaks' in root[e])
                    self.update_checkbox(status['nxcopy'], i, 
                        'nxcopy' in root[e] or self.is_parent(wrapper_file))
                    self.update_checkbox(status['nxrefine'], i,
                        'nxrefine' in root[e] or 
                        ('detector' in root[e]['instrument'] and 
                         'orientation_matrix' in root[e]['instrument/detector']))
                    self.update_checkbox(status['nxtransform'], i,
                        'nxtransform' in root[e] or 'transform' in root[e])
                else:
                    status['nxlink'].setEnabled(False)
                    status['nxmax'].setEnabled(False)
                    status['nxfind'].setEnabled(False)
                    status['nxcopy'].setEnabled(False)
                    status['nxrefine'].setEnabled(False)
                    status['nxtransform'].setEnabled(False)
                    status['reduce'].setEnabled(False)
                    status['overwrite'].setEnabled(False)
            self.update_checkbox(status['nxcombine'], 0,
                'nxcombine' in root['entry'] or 
                'transform' in root['entry'] or
                'masked_transform' in root['entry'])
            grid.addWidget(status['nxlink'], row, 1, QtCore.Qt.AlignHCenter)                   
            grid.addWidget(status['nxmax'], row, 2, QtCore.Qt.AlignHCenter)                   
            grid.addWidget(status['nxfind'], row, 3, QtCore.Qt.AlignHCenter)                   
            grid.addWidget(status['nxcopy'], row, 4, QtCore.Qt.AlignHCenter)                   
            grid.addWidget(status['nxrefine'], row, 5, QtCore.Qt.AlignHCenter)                   
            grid.addWidget(status['nxtransform'], row, 6, QtCore.Qt.AlignHCenter)                   
            grid.addWidget(status['nxcombine'], row, 7, QtCore.Qt.AlignHCenter)                   
            grid.addWidget(status['overwrite'], row, 8, QtCore.Qt.AlignHCenter)                  
            grid.addWidget(status['reduce'], row, 9, QtCore.Qt.AlignHCenter)                  
            self.scans[directory] = status
        row += 1
        grid.addWidget(QtWidgets.QLabel('All'), row, 0, QtCore.Qt.AlignHCenter)
        all_boxes = {}
        all_boxes['nxlink'] = self.new_checkbox(self.choose_all_scans)
        all_boxes['nxmax'] = self.new_checkbox(self.choose_all_scans)
        all_boxes['nxfind'] = self.new_checkbox(self.choose_all_scans)
        all_boxes['nxcopy'] = self.new_checkbox(self.choose_all_scans)
        all_boxes['nxrefine'] = self.new_checkbox(self.choose_all_scans)
        all_boxes['nxtransform'] = self.new_checkbox(self.choose_all_scans)
        all_boxes['nxcombine'] = self.new_checkbox(self.choose_all_scans)
        all_boxes['overwrite'] = self.new_checkbox(self.choose_all_scans)        
        all_boxes['reduce'] = self.new_checkbox(self.choose_all_scans)        
        grid.addWidget(all_boxes['nxlink'], row, 1, QtCore.Qt.AlignHCenter)                   
        grid.addWidget(all_boxes['nxmax'], row, 2, QtCore.Qt.AlignHCenter)                   
        grid.addWidget(all_boxes['nxfind'], row, 3, QtCore.Qt.AlignHCenter)                   
        grid.addWidget(all_boxes['nxcopy'], row, 4, QtCore.Qt.AlignHCenter)                   
        grid.addWidget(all_boxes['nxrefine'], row, 5, QtCore.Qt.AlignHCenter)                   
        grid.addWidget(all_boxes['nxtransform'], row, 6, QtCore.Qt.AlignHCenter)                   
        grid.addWidget(all_boxes['nxcombine'], row, 7, QtCore.Qt.AlignHCenter)                   
        grid.addWidget(all_boxes['overwrite'], row, 8, QtCore.Qt.AlignHCenter)
        grid.addWidget(all_boxes['reduce'], row, 9, QtCore.Qt.AlignHCenter)
        self.all_scans = all_boxes
        if self.grid:
            self.delete_grid(self.grid)
        self.grid = grid
        self.insert_layout(2, self.grid)           
        return grid

    def new_checkbox(self, slot=None):
        checkbox = QtWidgets.QCheckBox()
        checkbox.setCheckState(QtCore.Qt.Unchecked)
        checkbox.setEnabled(True)
        if slot:
            checkbox.stateChanged.connect(slot)
        return checkbox

    def update_checkbox(self, checkbox, idx, status):
        if status and idx == 0:
            checkbox.setCheckState(QtCore.Qt.Checked)
            checkbox.setEnabled(False)
        elif ((status and checkbox.checkState() == QtCore.Qt.Unchecked) or
              (not status and checkbox.checkState() == QtCore.Qt.Checked)):                    
            checkbox.setCheckState(QtCore.Qt.PartiallyChecked)
            checkbox.setEnabled(True)

    def choose_all_scans(self):
        for status in self.all_scans:
            for scan in self.scans:
                if self.scans[scan][status].isEnabled():
                    self.scans[scan][status].setCheckState(
                        self.all_scans[status].checkState())                

    def add_tasks(self):
        for scan in self.scans:
            if self.scans[scan]['reduce'].isChecked():
                for entry in ['f1', 'f2', 'f3']:
                    reduce = NXReduce(entry, scan)
                    if (not self.scans[scan]['nxlink'].isEnabled() or
                        not self.scans[scan]['nxlink'].isChecked()):
                        reduce.link = False
                    if (not self.scans[scan]['nxmax'].isEnabled() or
                        not self.scans[scan]['nxmax'].isChecked()):
                        reduce.maxcount = False
                    if (not self.scans[scan]['nxfind'].isEnabled() or 
                        not self.scans[scan]['nxfind'].isChecked()):
                        reduce.find = False
                    if (not self.scans[scan]['nxcopy'].isEnabled() or 
                        not self.scans[scan]['nxcopy'].isChecked()):
                        reduce.copy = False
                    if (self.scans[scan]['nxrefine'].isEnabled() and 
                        self.scans[scan]['nxrefine'].isChecked()):
                        reduce.refine = True
                    if self.scans[scan]['overwrite'].isChecked():
                        reduce.overwrite=True
                    reduce.queue()                            
