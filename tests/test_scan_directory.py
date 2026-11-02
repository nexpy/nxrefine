import os

import pytest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
QtWidgets = pytest.importorskip('qtpy.QtWidgets')
widgets = pytest.importorskip('nexpy.gui.widgets')

from nxrefine.plugins.experiment.add_scan import AddScanDialog  # noqa: E402
from nxrefine.plugins.experiment.new_scan import NewScanDialog  # noqa: E402

METHODS = ['scan_prefix', 'prefix', 'scan_units', 'scan_field', 'scan_label',
           'scan_value', 'scan_directory', 'scan_file',
           'get_scan_directory', 'update_scan', 'update_scan_labels',
           'connect_live_updates']


@pytest.fixture(scope='module')
def app():
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


@pytest.fixture
def new_scan(app):
    """The scan directory logic of the New Scan dialog without the dialog."""
    stub = type('NewScan', (), {name: NewScanDialog.__dict__[name]
                                for name in METHODS})()
    stub.sample = 'sample'
    stub.parameters = widgets.GridParameters()
    stub.parameters.add('parent', 'sample', 'Prefix')
    stub.parameters.add('scan_path', '/entry/sample/temperature', 'Scan Path')
    stub.parameters.add('scan_units', 'K', 'Scan Units')
    stub.scan_box = widgets.NXLineEdit('300')
    stub.scandir_box = widgets.NXLineEdit('')
    stub.scan_name_label = QtWidgets.QLabel()
    stub.scan_units_label = QtWidgets.QLabel()
    stub.connect_live_updates()
    stub.update_scan()
    return stub


def test_new_scan_directory_follows_the_prefix_as_it_is_typed(new_scan):
    assert new_scan.scan_directory == '300K'
    assert new_scan.scan_file == 'sample_300K.nxs'
    new_scan.parameters['parent'].box.setText('sample_cooling')
    assert new_scan.scan_directory == 'cooling_300K'
    assert new_scan.scan_file == 'sample_cooling_300K.nxs'


def test_new_scan_directory_follows_the_scan_value(new_scan):
    new_scan.scan_box.setText('2.5')
    assert new_scan.scan_directory == '2p5K'


def test_new_scan_directory_follows_the_units(new_scan):
    new_scan.parameters['scan_units'].box.setText('GPa')
    assert new_scan.scan_directory == '300GPa'
    assert new_scan.scan_units_label.text() == 'GPa'


def test_add_scan_directory_follows_the_scan_value(app):
    names = ['scan_value', 'scan_directory', 'scan_file', 'update_scan']
    stub = type('AddScan', (), {name: AddScanDialog.__dict__[name]
                                for name in names})()
    stub.sample = 'sample'
    stub.scan_units = 'K'
    stub.scandir_box = widgets.NXLineEdit('')
    stub.parent = type('Parent', (), {
        'get_scan_directory': lambda self, value: f"cooling_{value:g}K"})()
    stub.scan_box = widgets.NXLineEdit('300', slot=stub.update_scan)
    stub.scan_box.textChanged.connect(stub.update_scan)
    stub.update_scan()
    stub.scan_box.setText('250')
    assert stub.scan_directory == 'cooling_250K'
    assert stub.scan_file == 'sample_cooling_250K.nxs'
