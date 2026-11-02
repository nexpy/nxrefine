import numpy as np
import pytest
from nexusformat.nexus import (NXdetector, NXentry, NXinstrument,
                               NXmonochromator, nxopen)

from nxrefine.plugins.experiment.new_scan import default_q, format_q

WAVELENGTH = 0.14
DISTANCE = 650.0
PIXEL_SIZE = 0.172
SHAPE = [1679, 1475]


def q_range(beam_center_y):
    max_dist = max(beam_center_y, SHAPE[0] - 1 - beam_center_y)
    pix_to_q = 2 * np.pi * PIXEL_SIZE / (WAVELENGTH * DISTANCE)
    return 0.3 * max_dist * pix_to_q, 0.95 * max_dist * pix_to_q


def add_entry(root, name, beam_center_y=None):
    root[name] = NXentry()
    root[name]['instrument'] = NXinstrument()
    root[name]['instrument/monochromator'] = NXmonochromator(
        wavelength=WAVELENGTH)
    detector = NXdetector(distance=DISTANCE, pixel_size=PIXEL_SIZE,
                          shape=SHAPE)
    if beam_center_y is not None:
        detector['beam_center_x'] = 700.0
        detector['beam_center_y'] = beam_center_y
    root[name]['instrument/detector'] = detector


@pytest.fixture
def config(tmp_path):
    path = tmp_path / 'config.nxs'
    with nxopen(path, 'w') as root:
        add_entry(root, 'entry')
        add_entry(root, 'f1', 1000.0)
        add_entry(root, 'f2', 1100.0)
    return path


def test_default_q_uses_the_first_detector_entry(config):
    qmin, qmax = default_q(config)
    expected = q_range(1000.0)
    assert qmin == pytest.approx(expected[0])
    assert qmax == pytest.approx(expected[1])
    assert qmax > qmin > 0


def test_default_q_is_unavailable_without_a_beam_center(tmp_path):
    path = tmp_path / 'config.nxs'
    with nxopen(path, 'w') as root:
        add_entry(root, 'entry')
        add_entry(root, 'f1')
    assert default_q(path) == (None, None)


def test_default_q_is_unavailable_without_detector_entries(tmp_path):
    path = tmp_path / 'config.nxs'
    with nxopen(path, 'w') as root:
        add_entry(root, 'entry', 1000.0)
    assert default_q(path) == (None, None)


def test_default_q_handles_a_missing_file(tmp_path):
    assert default_q(tmp_path / 'missing.nxs') == (None, None)


@pytest.mark.parametrize('value, expected', [
    (5.165116, '5.2'), (16.356, '16.4'), (None, ''), ('', ''), (3, '3.0')])
def test_format_q(value, expected):
    assert format_q(value) == expected
