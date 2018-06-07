import os

from nexusformat.nexus import *
from nexpy.gui.pyqt import QtCore, QtWidgets
from nexpy.gui.datadialogs import BaseDialog, GridParameters
from nexpy.gui.utils import report_error, natural_sort

from nxrefine.nxreduce import Lock, NXReduce


def show_dialog():
    try:
        dialog = ParentDialog()
        dialog.show()
    except NeXusError as error:
        report_error("Choosing Parent", error)


class ParentDialog(BaseDialog):

    def __init__(self, parent=None):
        super(ParentDialog, self).__init__(parent)

        self.parameters = GridParameters()
        self.parameters.add('threshold', '', 'Threshold')
        self.parameters.add('first', '', 'First Frame')
        self.parameters.add('last', '', 'Last Frame')
        self.parameters.add('radius', 200, 'Radius')
        self.parameters.add('width', 3, 'Frame Width')

        self.set_layout(self.directorybox('Choose Sample Directory'),
                        self.filebox('Choose Parent File'),
                        self.parameters.grid(),
                        self.action_buttons(('Queue Reduction', self.add_tasks)),
                        self.close_buttons(close=True))
        self.set_title('Choose Parent')
        self.sample_directory = None

    def choose_directory(self):
        super(ParentDialog, self).choose_directory()
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

    def choose_file(self):
        super(ParentDialog, self).choose_file()
        self.make_parent()

    def make_parent(self):
        _parent = self.get_filename()
        _base = os.path.basename(os.path.splitext(_parent)[0])
        _scan = _base.replace(self.sample+'_', '')
        reduce = NXReduce(directory=os.path.join(self.sample_directory, _scan), 
                          overwrite=True)
        reduce.make_parent()

    @property
    def parent(self):
        _parent = self.get_filename()
        if os.path.isabs(_parent):
            return _parent
        else:
            return os.path.join(self.sample_directory, _parent)

    @property
    def threshold(self):
        try:
            _threshold = np.int32(self.parameters['threshold'].value)
            if _threshold > 0.0:
                return _threshold
            else:
                return None
        except Exception:
            return None

    @property
    def first(self):
        try:
            _first = np.int32(self.parameters['first'].value)
            if _first >= 0:
                return _first
            else:
                return None
        except Exception as error:
            return None

    @property
    def last(self):
        try:
            _last = np.int32(self.parameters['last'].value)
            if _last > 0:
                return _last
            else:
                return None
        except Exception as error:
            return None

    @property
    def radius(self):
        return self.parameters['radius'].value

    @property
    def width(self):
        return self.parameters['width'].value

    def add_tasks(self):
        with Lock(self.parent):
            root = nxload(self.parent)
        for entry in [e for e in root.entries if e != 'entry']:
            reduce = NXReduce(root[entry], link=True, maxcount=True, find=True, 
                              mask3D=True, first=self.first, last=self.last, 
                              threshold=self.threshold, 
                              radius=self.radius, width=self.width)
            reduce.queue(parent=True)                            
