import datetime
import glob
import os
import re
import sys
import time
import timeit
from datetime import datetime
from ConfigParser import ConfigParser

from nexpy.gui.pyqt import QtCore, QtGui, getOpenFileName
import numpy as np

from nexpy.gui.importdialog import BaseImportDialog
from nexpy.gui.mainwindow import report_error
from nexpy.readers.tifffile import tifffile as TIFF
from nexusformat.nexus import *


prefix_pattern = re.compile('^([^.]+)(?:(?<!\d)|(?=_))')
index_pattern = re.compile('^(.*?)([0-9]*)[.](.*)$')

maximum = 0.0


def show_dialog():
#    try:
    dialog = StackDialog()
    dialog.show()
#    except NeXusError as error:
#        report_error("Stacking Images", error)

def isotime(time_stamp):
    return datetime.fromtimestamp(time_stamp).isoformat()

def epoch(iso_time):
    d = datetime.strptime(iso_time,'%Y-%m-%dT%H:%M:%S.%f')
    return time.mktime(d.timetuple()) + (d.microsecond / 1e6)


class StackDialog(BaseImportDialog):
    """Dialog to import an image stack (TIFF or CBF)"""
 
    def __init__(self, parent=None):

        super(StackDialog, self).__init__(parent)
        
        status_layout = QtGui.QHBoxLayout()
        self.progress_bar = QtGui.QProgressBar()
        status_layout.addWidget(self.progress_bar)
        self.progress_bar.setVisible(False)
        status_layout.addStretch()
        status_layout.addWidget(self.close_buttons(save=True))

        self.set_layout(self.directorybox(), 
                        self.make_filter_box(),
                        self.make_range_box(),
                        self.make_output_box(),
                        status_layout)

        self.setLayout(self.layout)
        self.set_title('Stack Images')
  
        self.suffix = ''

    def make_filter_box(self):
        filter_box = QtGui.QWidget()
        layout = QtGui.QGridLayout()
        layout.setSpacing(10)
        prefix_label = QtGui.QLabel('File Prefix')
        self.prefix_box = QtGui.QLineEdit()
        self.prefix_box.editingFinished.connect(self.set_range)
        extension_label = QtGui.QLabel('File Extension')
        self.extension_box = QtGui.QLineEdit()
        self.extension_box.editingFinished.connect(self.set_extension)
        suffix_label = QtGui.QLabel('File Suffix')
        self.suffix_box = QtGui.QLineEdit('')
        self.suffix_box.editingFinished.connect(self.get_prefixes)
        layout.addWidget(prefix_label, 0, 0)
        layout.addWidget(self.prefix_box, 0, 1)
        layout.addWidget(extension_label, 0, 2)
        layout.addWidget(self.extension_box, 0, 3)
        layout.addWidget(suffix_label, 0, 4)
        layout.addWidget(self.suffix_box, 0, 5)
        self.prefix_combo = QtGui.QComboBox()
        self.prefix_combo.setSizeAdjustPolicy(QtGui.QComboBox.AdjustToContents)
        self.prefix_combo.activated.connect(self.choose_prefix)
        self.extension_combo = QtGui.QComboBox()
        self.extension_combo.setSizeAdjustPolicy(QtGui.QComboBox.AdjustToContents)
        self.extension_combo.activated.connect(self.choose_extension)
        layout.addWidget(self.prefix_combo, 1, 1, alignment=QtCore.Qt.AlignHCenter)
        layout.addWidget(self.extension_combo, 1, 3, alignment=QtCore.Qt.AlignHCenter)

        filter_box.setLayout(layout)
        filter_box.setVisible(False)
        return filter_box

    @property
    def suffix(self):
        return self.suffix_box.text()

    def make_range_box(self):
        range_box = QtGui.QWidget()
        layout = QtGui.QHBoxLayout()
        rangeminlabel = QtGui.QLabel("Min. index")
        self.rangemin = QtGui.QLineEdit()
        self.rangemin.setFixedWidth(150)
        self.rangemin.setAlignment(QtCore.Qt.AlignRight)
        rangemaxlabel = QtGui.QLabel("Max. index")
        self.rangemax = QtGui.QLineEdit()
        self.rangemax.setFixedWidth(150)
        self.rangemax.setAlignment(QtCore.Qt.AlignRight)
        layout.addWidget(rangeminlabel)
        layout.addWidget(self.rangemin)
        layout.addStretch()
        layout.addWidget(rangemaxlabel)
        layout.addWidget(self.rangemax)
 
        range_box.setLayout(layout)
        range_box.setVisible(False)
        return range_box

    def make_output_box(self):
        """
        Creates a text box and button for selecting the output file.
        """
        output_box = QtGui.QWidget()
        layout = QtGui.QHBoxLayout()
       
        file_button =  QtGui.QPushButton("Choose Output File")
        file_button.clicked.connect(self.choose_output_file)
        self.output_file = QtGui.QLineEdit(self)
        self.output_file.setMinimumWidth(300)
        layout.addWidget(file_button)
        layout.addWidget(self.output_file)

        output_box.setLayout(layout)
        output_box.setVisible(False)
        return output_box
 
    def choose_directory(self):
        super(StackDialog, self).choose_directory()
        files = self.get_filesindirectory()
        self.get_extensions()
        self.get_prefixes()
        self.filter_box.setVisible(True)
        self.output_box.setVisible(True)

    def choose_output_file(self):
        """
        Opens a file dialog and sets the settings file text box to the chosen path.
        """
        dirname = self.get_default_directory(self.get_output_file())
        filename = getOpenFileName(self, 'Choose Output File', dirname, 
                                   self.nexus_filter)
        if os.path.exists(dirname):    # avoids problems if <Cancel> was selected
            self.output_file.setText(filename)
            self.set_default_directory(dirname)

    def get_prefixes(self):
        files = [f for f in self.get_filesindirectory() 
                     if f.endswith(self.get_extension())]
        self.prefix_combo.clear()        
        prefixes = []
        for file in files:
            prefix = prefix_pattern.match(file)
            if prefix:
                prefixes.append(prefix.group(0).strip('_-'))
        for prefix in set(prefixes):
            if prefix != '':
                self.prefix_combo.addItem(prefix)
        if self.get_prefix() not in prefixes:
            self.set_prefix(prefixes[0])
        self.prefix_combo.setCurrentIndex(self.prefix_combo.findText(self.get_prefix()))
        try:
            files = [f for f in files if f.startswith(self.get_prefix())]
            min, max = self.get_index(files[0]), self.get_index(files[-1])
            if max < min:
                raise ValueError
            self.set_indices(min, max)
            self.range_box.setVisible(True)
        except Exception as error:
            self.set_indices('', '')
            self.range_box.setVisible(False)

    def get_prefix(self):
        return self.prefix_box.text().strip()
 
    def choose_prefix(self):
        self.set_prefix(self.prefix_combo.currentText())
     
    def set_prefix(self, text):
        self.prefix_box.setText(text)
        if self.prefix_combo.findText(text) >= 0:
            self.prefix_combo.setCurrentIndex(self.prefix_combo.findText(text))
        self.output_file.setText(os.path.join(self.get_directory(), text+'.nxs'))
        self.get_prefixes()
 
    def get_extensions(self):
        files = self.get_filesindirectory()
        extensions =  set([os.path.splitext(f)[-1] for f in files])
        self.extension_combo.clear()
        for extension in extensions:
            self.extension_combo.addItem(extension)
        if not self.get_extension() or not self.get_extension() in extensions:
            if '.tif' in extensions:
                self.set_extension('.tif')
            elif '.tiff' in extensions:
                self.set_extension('.tiff')
            elif '.cbf' in extensions:
                self.set_extension('.cbf')
        self.extension_combo.setCurrentIndex(self.extension_combo.findText(self.get_extension()))
        return extensions

    def get_extension(self):
        extension = self.extension_box.text().strip()
        if extension and not extension.startswith('.'):
            extension = '.'+extension
        return extension

    def choose_extension(self):
        self.set_extension(self.extension_combo.currentText())
     
    def set_extension(self, text):
        if not text.startswith('.'):
            text = '.'+text
        self.extension_box.setText(text)
        if self.extension_combo.findText(text) >= 0:
            self.extension_combo.setCurrentIndex(self.extension_combo.findText(text))
        self.get_prefixes()

    def get_image_type(self):
        if self.get_extension() == '.cbf':
            return 'CBF'
        else:
            return 'TIFF'

    def get_index(self, file):
        return int(re.match('^(.*?)([0-9]*)%s[.](.*)$' % self.suffix, 
                               file).groups()[1])

    def get_indices(self):
        try:
            min, max = (int(self.rangemin.text().strip()),
                        int(self.rangemax.text().strip()))
            return min, max
        except:
            return None

    def set_indices(self, min, max):
        self.rangemin.setText(str(min))
        self.rangemax.setText(str(max))

    def get_output_file(self):
        return self.output_file.text()

    def get_files(self):
        prefix = self.get_prefix()
        filenames = self.get_filesindirectory(prefix, 
                                              self.get_extension())
        if self.get_indices():
            min, max = self.get_indices()
            return [file for file in filenames if self.get_index(file) >= min and 
                                                  self.get_index(file) <= max]
        else:
            return filenames

    def set_range(self):
        files = self.get_filesindirectory(self.get_prefix(), self.get_extension())
        try:
            min, max = self.get_index(files[0]), self.get_index(files[-1])
            if min > max:
                raise ValueError
            self.set_indices(min, max)
            self.range_box.setVisible(True)
        except:
            self.set_indices('', '')
            self.range_box.setVisible(False)

    def read_image(self, filename):
        if self.get_image_type() == 'CBF':
            import pycbf
            cbf = pycbf.cbf_handle_struct()
            cbf.read_file(str(filename), pycbf.MSG_DIGEST)
            cbf.select_datablock(0)
            cbf.select_category(0)
            cbf.select_column(2)
            imsize = cbf.get_image_size(0)
            return np.fromstring(cbf.get_integerarray_as_string(),np.int32).reshape(imsize)
        else:
            from nexpy.readers.tifffile import tifffile as TIFF
            return TIFF.imread(filename)

    def read_images(self, filenames):
        if self.get_image_type() == 'CBF':
            v0 = self.read_image(filenames[0])
            v = np.zeros([len(filenames), v0.shape[0], v0.shape[1]], dtype=np.int32)
            for i,filename in enumerate(filenames):
                v[i] = self.read_image(filename)
        else:
            from nexpy.readers.tifffile import tifffile as TIFF
            v = TIFF.TiffSequence(filenames).asarray()        
        global maximum
        if v.max() > maximum:
            maximum = v.max()
        return v

    def get_data(self):
        filenames = self.get_files()
        v0 = self.read_image(filenames[0])
        x = NXfield(range(v0.shape[1]), dtype=np.uint16, name='x')
        y = NXfield(range(v0.shape[0]), dtype=np.uint16, name='y')
        z = NXfield(range(1,len(filenames)+1), dtype=np.uint16, name='z')
        v = NXfield(shape=(len(filenames),v0.shape[0],v0.shape[1]),
                    dtype=v0.dtype, name='v')
        v[0] = v0
        if v._memfile:
            chunk_size = v._memfile['data'].chunks[0]
        else:
            chunk_size = v.shape[0]/10
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, len(filenames))
        for i in range(0, len(filenames)):
            try:
                files = []
                for j in range(i,i+chunk_size):
                    files.append(filenames[j])
                    self.progress_bar.setValue(j)
                self.update_progress()
                v[i:i+chunk_size,:,:] = self.read_images(files)
            except IndexError as error:
                pass
        global maximum
        v.maximum = maximum
        self.progress_bar.setVisible(False)
        return NXroot(NXentry(NXdata(v,(z,y,x))))

    def accept(self):
#        try:
        output_file = self.get_output_file()
        try:
            output_file = self.get_output_file()
            try:
                workspace = self.treeview.tree.get_name(os.path.basename(output_file))
            except Exception:
                workspace = self.treeview.tree.get_new_name()
            self.treeview.tree[workspace] = self.user_ns[workspace] = self.get_data()
            super(StackDialog, self).accept()
        except NeXusError as error:
            report_error("Stacking Images", error)
