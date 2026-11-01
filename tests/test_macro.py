from types import SimpleNamespace

import pytest
from nexusformat.nexus import (NXdetector, NXentry, NXfield, NXgoniometer,
                               NXinstrument, NXsample, nxopen)

from nxrefine import nxbeamline
from nxrefine.nxbeamline import Sector6Beamline, scan_temperature


@pytest.mark.parametrize('scan_dir, expected', [
    ('300K', '300'),
    ('2p5K', '2p5'),
    ('12p25K', '12p25'),
    ('m5K', 'm5'),
    ('atten_300K', '300'),
    ('run2_2p5K', '2p5'),
    ('25GPa', '25'),
    ('300', '300'),
    ('background', 'background'),
])
def test_scan_temperature(scan_dir, expected):
    assert scan_temperature(scan_dir) == expected


@pytest.fixture
def beamline(tmp_path, monkeypatch):
    settings = {'instrument': {'experiment': 'exp', 'raw_home': '/raw',
                               'raw_path': 'data'}}
    monkeypatch.setattr(nxbeamline, 'NXSettings',
                        lambda directory=None: SimpleNamespace(
                            settings=settings))
    label_dir = tmp_path / 'sample' / 'label'
    label_dir.mkdir(parents=True)
    return Sector6Beamline(directory=label_dir), label_dir


def make_scan_file(label_dir, scan_dir, temperature):
    scan_file = label_dir / f"sample_{scan_dir}.nxs"
    with nxopen(scan_file, 'w') as root:
        root['entry'] = NXentry()
        root['entry/sample'] = NXsample(temperature=temperature)
    return scan_file


def test_macro_lines_use_scan_directory(beamline):
    instance, label_dir = beamline
    scan_files = [make_scan_file(label_dir, '300K', 300.0),
                  make_scan_file(label_dir, '2p5K', 2.5),
                  make_scan_file(label_dir, '12K', 12.0)]
    lines = instance.create_macro(scan_files, 'Tscan')
    assert lines[1:] == ['Tscan  300', 'Tscan  2p5', 'Tscan  12']


def test_macro_follows_the_order_given(beamline):
    instance, label_dir = beamline
    scan_files = [make_scan_file(label_dir, '300K', 300.0),
                  make_scan_file(label_dir, '2p5K', 2.5)]
    lines = instance.create_macro(list(reversed(scan_files)), 'Tscan')
    assert lines[1:] == ['Tscan  2p5', 'Tscan  300']


def test_pil2mstring_is_unchanged(beamline):
    instance, label_dir = beamline
    scan_files = [make_scan_file(label_dir, '2p5K', 2.5)]
    lines = instance.create_macro(scan_files, 'Pil2Mstring')
    assert lines[1:] == ['Pil2Mstring("2p5K")']


def add_scan_entry(scan_file, name='f1'):
    with nxopen(scan_file, 'rw') as root:
        root[name] = NXentry()
        root[name]['instrument'] = NXinstrument()
        root[name]['instrument/goniometer'] = NXgoniometer()
        phi = NXfield(-5.0)
        phi.attrs['step'] = 0.1
        phi.attrs['end'] = 360.0
        root[name]['instrument/goniometer/phi'] = phi
        root[name]['instrument/goniometer/chi'] = 0.0
        root[name]['instrument/goniometer/omega'] = 1.5
        root[name]['instrument/detector'] = NXdetector()
        root[name]['instrument/detector/translation_x'] = 2.0
        root[name]['instrument/detector/translation_y'] = 3.0


def test_pil2mscan_names_the_scan_directory_and_entry(beamline):
    instance, label_dir = beamline
    scan_file = make_scan_file(label_dir, '2p5K', 2.5)
    add_scan_entry(scan_file)
    add_scan_entry(scan_file, 'f2')
    lines = instance.create_macro([scan_file], 'Pil2Mscan')
    assert lines[1:] == [
        f"Pil2Mscan {label_dir / '2p5K'} f1 2.5 2 3 -5 0.1 360 0 1.5 10",
        f"Pil2Mscan {label_dir / '2p5K'} f2 2.5 2 3 -5 0.1 360 0 1.5 10"]
