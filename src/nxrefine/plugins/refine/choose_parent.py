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
        self.parameters.add('radius', '', 'Radius')
        self.parameters.add('width', '', 'Frame Width')

        self.set_layout(self.directorybox('Choose Sample Directory', default=False),
                        self.filebox('Choose Parent File'),
                        self.parameters.grid(),
                        self.action_buttons(('Add to Queue', self.add_tasks)),
                        self.close_buttons(close=True))
        self.set_title('Choose Parent')
        self.sample_directory = None
        self.old_parent = None

    def choose_directory(self):
        super(ParentDialog, self).choose_directory()
        self.sample_directory = self.get_directory()
        self.sample = os.path.basename(os.path.dirname(self.sample_directory))
        parent_file = os.path.join(self.sample_directory, 
                                   self.sample+'_parent.nxs')
        if os.path.exists(parent_file):
            self.filename.setText(os.path.basename(os.path.realpath(parent_file)))
            self.old_parent = self.parent
            self.update_parameters()
        else:
            self.filename.setText('')
        self.root_directory = os.path.dirname(os.path.dirname(self.sample_directory))
        self.mainwindow.default_directory = self.sample_directory

    def choose_file(self):
        super(ParentDialog, self).choose_file()
        self.make_parent()

    def make_parent(self):
        self.reduce.make_parent()
        self.update_parameters

    def update_parameters(self):
        reduce = self.reduce
        if reduce.first:
            self.parameters['first'].value = reduce.first
        if reduce.last:
            self.parameters['last'].value = reduce.last
        if reduce.threshold:
            self.parameters['threshold'].value = reduce.threshold
        if reduce.radius:
            self.parameters['radius'].value = reduce.radius
        if reduce.width:
            self.parameters['width'].value = reduce.width

    @property
    def reduce(self):
        _parent = self.get_filename()
        _base = os.path.basename(os.path.splitext(_parent)[0])
        _scan = _base.replace(self.sample+'_', '')
        return NXReduce(directory=os.path.join(self.sample_directory, _scan), 
                        overwrite=True)

    @property
    def parent(self):
        _parent = self.get_filename()
        if os.path.isabs(_parent):
            return _parent
        else:
            return os.path.join(self.sample_directory, _parent)

    @property
    def threshold(self):
        return self.parameters['threshold'].value

    @property
    def first(self):
        return self.parameters['first'].value

    @property
    def last(self):
        return self.parameters['last'].value

    @property
    def radius(self):
        return self.parameters['radius'].value

    @property
    def width(self):
        return self.parameters['width'].value

    def add_tasks(self):
        if self.parent == self.old_parent:
            return
        with Lock(self.parent):
            root = nxload(self.parent)
        for entry in [e for e in root.entries if e != 'entry']:
            reduce = NXReduce(root[entry], link=True, maxcount=True, find=True, 
                              mask3D=True, first=self.first, last=self.last, 
                              threshold=self.threshold, 
                              radius=self.radius, width=self.width)
            reduce.queue(parent=True)
        self.old_parent = self.parent                          
