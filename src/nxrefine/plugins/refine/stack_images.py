# -----------------------------------------------------------------------------
# Copyright (c) 2015-2021, NeXpy Development Team.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file COPYING, distributed with this software.
# -----------------------------------------------------------------------------

import os
import re
import time
from datetime import datetime

import numpy as np
from nexpy.gui.importdialog import BaseImportDialog
from nexpy.gui.pyqt import QtCore, QtWidgets, getOpenFileName
from nexpy.gui.utils import report_error
from nexpy.gui.widgets import NXLabel, NXLineEdit
from nexusformat.nexus import (NeXusError, NXcollection, NXdata, NXentry,
                               NXfield, NXnote, NXroot)

prefix_pattern = re.compile(r'^([^.]+)(?:(?<!\d)|(?=_))')
index_pattern = re.compile(r'^(.*?)([0-9]*)[.](.*)$')

maximum = 0.0


def show_dialog():
    try:
        dialog = StackDialog()
        dialog.show()
    except NeXusError as error:
        report_error("Stacking Images", error)


def isotime(time_stamp):
    return datetime.fromtimestamp(time_stamp).isoformat()


def epoch(iso_time):
    d = datetime.strptime(iso_time, '%Y-%m-%dT%H:%M:%S.%f')
    return time.mktime(d.timetuple()) + (d.microsecond / 1e6)


class StackDialog(BaseImportDialog):
    """Dialog to import an image stack (TIFF or CBF)"""

    def __init__(self, parent=None):

        super().__init__(parent)

        status_layout = QtWidgets.QHBoxLayout()
        self.progress_bar = QtWidgets.QProgressBar()
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
        filter_box = QtWidgets.QWidget()
        layout = QtWidgets.QGridLayout()
        layout.setSpacing(10)
        prefix_label = NXLabel('File Prefix')
        self.prefix_box = NXLineEdit(slot=self.set_range)
        extension_label = NXLabel('File Extension')
        self.extension_box = NXLineEdit(slot=self.set_extension)
        suffix_label = NXLabel('File Suffix')
        self.suffix_box = NXLineEdit(slot=self.get_prefixes)
        layout.addWidget(prefix_label, 0, 0)
        layout.addWidget(self.prefix_box, 0, 1)
        layout.addWidget(extension_label, 0, 2)
        layout.addWidget(self.extension_box, 0, 3)
        layout.addWidget(suffix_label, 0, 4)
        layout.addWidget(self.suffix_box, 0, 5)
        self.prefix_combo = QtWidgets.QComboBox()
        self.prefix_combo.setSizeAdjustPolicy(
            QtWidgets.QComboBox.AdjustToContents)
        self.prefix_combo.activated.connect(self.choose_prefix)
        self.extension_combo = QtWidgets.QComboBox()
        self.extension_combo.setSizeAdjustPolicy(
            QtWidgets.QComboBox.AdjustToContents)
        self.extension_combo.activated.connect(self.choose_extension)
        layout.addWidget(self.prefix_combo, 1, 1,
                         alignment=QtCore.Qt.AlignHCenter)
        layout.addWidget(self.extension_combo, 1, 3,
                         alignment=QtCore.Qt.AlignHCenter)

        filter_box.setLayout(layout)
        filter_box.setVisible(False)
        return filter_box

    @property
    def suffix(self):
        return self.suffix_box.text()

    def make_range_box(self):
        range_box = QtWidgets.QWidget()
        layout = QtWidgets.QHBoxLayout()
        rangeminlabel = NXLabel("Min. index")
        self.rangemin = NXLineEdit(width=150, align='right')
        rangemaxlabel = NXLabel("Max. index")
        self.rangemax = NXLineEdit(width=150, align='right')
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
        output_box = QtWidgets.QWidget()
        layout = QtWidgets.QHBoxLayout()

        file_button = QtWidgets.QPushButton("Choose Output File")
        file_button.clicked.connect(self.choose_output_file)
        self.output_file = NXLineEdit(parent=self)
        self.output_file.setMinimumWidth(300)
        layout.addWidget(file_button)
        layout.addWidget(self.output_file)

        output_box.setLayout(layout)
        output_box.setVisible(False)
        return output_box

    def choose_directory(self):
        super().choose_directory()
        files = self.get_filesindirectory()
        self.get_extensions()
        self.get_prefixes()
        self.filter_box.setVisible(True)
        self.output_box.setVisible(True)

    def choose_output_file(self):
        """
        Open a file dialog and set the settings file to the chosen path.
        """
        dirname = self.get_default_directory(self.get_output_file())
        filename = getOpenFileName(self, 'Choose Output File', dirname,
                                   self.nexus_filter)
        if os.path.exists(dirname):  # avoids problems if <Cancel> was selected
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
        self.prefix_combo.setCurrentIndex(
            self.prefix_combo.findText(self.get_prefix()))
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
        self.output_file.setText(os.path.join(
            self.get_directory(), text+'.nxs'))
        self.get_prefixes()

    def get_extensions(self):
        files = self.get_filesindirectory()
        extensions = set([os.path.splitext(f)[-1] for f in files])
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
        self.extension_combo.setCurrentIndex(
            self.extension_combo.findText(self.get_extension()))
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
            self.extension_combo.setCurrentIndex(
                self.extension_combo.findText(text))
        self.get_prefixes()

    def get_image_type(self):
        if self.get_extension() == '.cbf':
            return 'CBF'
        else:
            return 'TIFF'

    def get_index(self, file):
        return int(re.match(f'^(.*?)([0-9]*){self.suffix}[.](.*)$',
                            file).groups()[1])

    def get_indices(self):
        try:
            min, max = (int(self.rangemin.text().strip()),
                        int(self.rangemax.text().strip()))
            return min, max
        except Exception:
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
            return [file for file in filenames
                    if self.get_index(file) >= min
                    and self.get_index(file) <= max]
        else:
            return filenames

    def set_range(self):
        files = self.get_filesindirectory(
            self.get_prefix(), self.get_extension())
        try:
            min, max = self.get_index(files[0]), self.get_index(files[-1])
            if min > max:
                raise ValueError
            self.set_indices(min, max)
            self.range_box.setVisible(True)
        except Exception:
            self.set_indices('', '')
            self.range_box.setVisible(False)

    def read_image(self, filename):
        try:
            import fabio
        except ImportError:
            raise NeXusError("Please install the 'fabio' module")
        im = fabio.open(filename)
        return im

    def read_images(self, filenames):
        v0 = self.read_image(filenames[0]).data
        v = np.zeros(
            [len(filenames),
             v0.shape[0],
             v0.shape[1]],
            dtype=np.int32)
        for i, filename in enumerate(filenames):
            v[i] = self.read_image(filename).data
        global maximum
        if v.max() > maximum:
            maximum = v.max()
        return v

    def get_data(self):
        filenames = self.get_files()
        im = self.read_image(filenames[0])
        v0 = im.data
        x = NXfield(range(v0.shape[1]), dtype=np.uint16, name='x')
        y = NXfield(range(v0.shape[0]), dtype=np.uint16, name='y')
        z = NXfield(range(1, len(filenames)+1), dtype=np.uint16, name='z')
        v = NXfield(shape=(len(filenames), v0.shape[0], v0.shape[1]),
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
                for j in range(i, i+chunk_size):
                    files.append(filenames[j])
                    self.progress_bar.setValue(j)
                self.update_progress()
                v[i:i+chunk_size, :, :] = self.read_images(files)
            except IndexError as error:
                pass
        global maximum
        v.maximum = maximum
        self.progress_bar.setVisible(False)

        if im.getclassname() == 'CbfImage':
            note = NXnote(type='text/plain', file_name=self.import_file)
            note.data = im.header.pop('_array_data.header_contents', '')
            note.description = im.header.pop(
                '_array_data.header_convention', '')
        else:
            note = None

        header = NXcollection()
        for key, value in im.header.items():
            header[key] = value

        if note:
            entry = NXentry(
                NXdata(
                    v, (z, y, x),
                    CBF_header=note, header=header))
        else:
            entry = NXentry(NXdata(v, (z, y, x), header=header))

        return NXroot(entry)

    def accept(self):
        try:
            output_file = self.get_output_file()
            try:
                workspace = self.treeview.tree.get_name(
                    os.path.basename(output_file))
            except Exception:
                workspace = self.treeview.tree.get_new_name()
            self.treeview.tree[workspace] = self.user_ns[workspace] = (
                self.get_data())
            super().accept()
        except NeXusError as error:
            report_error("Stacking Images", error)
