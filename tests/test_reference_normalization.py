import numpy as np
import pytest
from nexusformat.nexus import NeXusError, NXdata, NXentry, NXfield

from nxrefine.nxreduce import BASELINE_WEIGHT, PARTIAL_METHOD, NXReduce
from test_parent_sync import make_registry


class FakeReduce:
    """Minimal stand-in exposing the normalization methods."""

    use_monitor = NXReduce.use_monitor
    reference_monitor = NXReduce.reference_monitor
    get_reference_level = NXReduce.get_reference_level
    get_sample_transmission = NXReduce.get_sample_transmission
    calculate_transmission = NXReduce.calculate_transmission
    update_reference = NXReduce.update_reference
    write_transmission = NXReduce.write_transmission
    _find_transmission = staticmethod(NXReduce._find_transmission)
    _transmission_attr = staticmethod(NXReduce._transmission_attr)
    _transmission_median = staticmethod(NXReduce._transmission_median)

    def __init__(self, parent, scan, monitor='none', norm=30000.0,
                 baseline=None, median=None, median_monitor=None,
                 method=PARTIAL_METHOD, first=True, nframes=2,
                 monitor_signal=None, baseline_weight=BASELINE_WEIGHT):
        self.parent = parent
        self.wrapper_file = parent.filename.with_name(f'{scan}.nxs')
        self.monitor = monitor
        self.norm = norm
        self.nframes = nframes
        self.first = 0
        self.last = nframes
        self.baseline_weight = baseline_weight
        self.partial_frames = None
        self.messages = []
        self._first = first
        self.entries = ['f1', 'f2']
        self.entry = NXentry()
        self.scan_entry = self.entry
        self.first_signal = None
        self._monitor_signal = (np.ones(nframes) if monitor_signal is None
                                else np.asarray(monitor_signal, dtype=float))
        if baseline is not None:
            self.entry['frame_sums'] = NXentry()
            self.entry['frame_sums/transmission'] = NXdata(
                self.make_signal(baseline, median, median_monitor, method))

    @staticmethod
    def make_signal(baseline, median, median_monitor=None,
                    method=PARTIAL_METHOD):
        signal = NXfield(np.asarray(baseline, dtype=float),
                         name='transmission')
        if median is not None:
            signal.attrs['median'] = median
        if median_monitor is not None:
            signal.attrs['median_monitor'] = median_monitor
        if method is not None:
            signal.attrs['method'] = method
        return signal

    def read_monitor(self):
        return self._monitor_signal

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def _get_reduce_target(self):
        return self.entry

    def consolidate(self, groups):
        self.consolidated = [group.nxname for group in groups]

    def log(self, message):
        self.messages.append(message)

    def is_first_entry(self):
        return self._first

    def _get_entry_target(self, name):
        group = NXentry()
        if self.first_signal is not None:
            group['frame_sums'] = NXentry()
            group['frame_sums/transmission'] = NXdata(self.first_signal)
        return group


def make_parent(tmp_path, scans=('s1', 's2')):
    return make_registry(tmp_path / 'sample_scans.nxs', scans=scans)


def claim(parent, scan, level, monitor='none', norm=30000.0,
          level_monitor=None, **kwargs):
    return parent.claim_reference(scan, level, monitor, norm,
                                  level_monitor=level_monitor,
                                  method=PARTIAL_METHOD, **kwargs)


def test_monitor_switched_off_by_blank_setting(tmp_path):
    parent = make_parent(tmp_path)
    for value in ('', '  ', 'None', 'none'):
        assert not FakeReduce(parent, 's1', monitor=value).use_monitor
    assert FakeReduce(parent, 's1', monitor='MCS2').use_monitor


def test_first_scan_claims_reference_and_second_does_not(tmp_path):
    parent = make_parent(tmp_path)
    assert parent.reference is None
    assert claim(parent, 's1', 2.0, level_monitor=3.0, monitor='MCS2')
    assert not claim(parent, 's2', 5.0)
    reference = parent.reference
    assert reference['reference_scan'] == 's1'
    assert reference['reference_level'] == 2.0
    assert reference['reference_level_monitor'] == 3.0
    assert reference['reference_monitor'] == 'MCS2'
    assert reference['reference_method'] == PARTIAL_METHOD


def test_reference_can_be_forced_and_refreshed(tmp_path):
    parent = make_parent(tmp_path)
    claim(parent, 's1', 2.0, level_monitor=3.0)
    assert claim(parent, 's1', 4.0)
    reference = parent.reference
    assert reference['reference_level'] == 4.0
    assert 'reference_level_monitor' not in reference
    assert claim(parent, 's2', 5.0, force=True)
    assert parent.reference['reference_scan'] == 's2'


def test_update_reference_respects_set_reference(tmp_path):
    parent = make_parent(tmp_path)
    one = FakeReduce(parent, 's1', baseline=np.ones(2), median=2.0)
    two = FakeReduce(parent, 's2', baseline=np.ones(2), median=4.0)
    transmission_one = one.entry['frame_sums/transmission']
    transmission_two = two.entry['frame_sums/transmission']
    one.update_reference(transmission_one, set_reference=False)
    assert parent.reference is None
    one.update_reference(transmission_one)
    assert parent.reference['reference_level'] == 2.0
    two.update_reference(transmission_two)
    assert parent.reference['reference_scan'] == 's1'
    two.update_reference(transmission_two, set_reference=True)
    assert parent.reference['reference_scan'] == 's2'
    one.update_reference(transmission_one, set_reference=False)
    assert parent.reference['reference_scan'] == 's2'


def test_update_reference_ignores_other_entries(tmp_path):
    parent = make_parent(tmp_path)
    other = FakeReduce(parent, 's1', baseline=np.ones(2), median=2.0,
                       first=False)
    other.update_reference(other.entry['frame_sums/transmission'])
    assert parent.reference is None


def test_transmission_scaled_to_reference(tmp_path):
    parent = make_parent(tmp_path)
    claim(parent, 's1', 8.0)
    reduce = FakeReduce(parent, 's2', baseline=[1.0, 0.5], median=4.0)
    np.testing.assert_allclose(reduce.get_sample_transmission(), [0.5, 0.25])


def test_monitor_is_applied_to_the_baseline(tmp_path):
    parent = make_parent(tmp_path)
    claim(parent, 's1', 8.0, level_monitor=2.0, monitor='MCS2')
    reduce = FakeReduce(parent, 's2', monitor='MCS2', baseline=[1.0, 0.5],
                        median=4.0, monitor_signal=[2.0, 1.0])
    np.testing.assert_allclose(reduce.get_sample_transmission(), [1.0, 1.0])


def test_monitor_mismatch_ignores_reference(tmp_path):
    parent = make_parent(tmp_path)
    claim(parent, 's1', 8.0, level_monitor=2.0, monitor='MCS1')
    reduce = FakeReduce(parent, 's2', monitor='MCS2', baseline=[1.0, 1.0],
                        median=4.0, median_monitor=4.0)
    assert reduce.get_reference_level() is None
    np.testing.assert_allclose(reduce.get_sample_transmission(), [1.0, 1.0])
    assert reduce.messages


def test_monitor_off_reference_does_not_depend_on_monitor(tmp_path):
    parent = make_parent(tmp_path)
    claim(parent, 's1', 8.0, monitor='MCS1')
    reduce = FakeReduce(parent, 's2', monitor='', norm=1234.0)
    assert reduce.get_reference_level() == 8.0


def test_reference_of_another_method_is_ignored(tmp_path):
    parent = make_parent(tmp_path)
    parent.claim_reference('s1', 8.0, 'none', 30000.0, method='other')
    reduce = FakeReduce(parent, 's2', baseline=[1.0, 1.0], median=4.0)
    assert reduce.get_reference_level() is None
    assert reduce.messages


def test_without_reference_other_entries_follow_first_entry(tmp_path):
    parent = make_parent(tmp_path)
    first = FakeReduce.make_signal(np.ones(2), 2.0)
    reduce = FakeReduce(parent, 's1', baseline=[1.0, 1.0], median=3.0,
                        first=False)
    reduce.first_signal = first
    np.testing.assert_allclose(reduce.get_sample_transmission(), [1.5, 1.5])
    reduce = FakeReduce(parent, 's1', baseline=[1.0, 1.0], median=3.0)
    np.testing.assert_allclose(reduce.get_sample_transmission(), [1.0, 1.0])


def test_transmission_of_another_method_has_median_of_one(tmp_path):
    parent = make_parent(tmp_path)
    claim(parent, 's1', 8.0)
    first = FakeReduce.make_signal(np.ones(2), 2.0, method=None)
    reduce = FakeReduce(parent, 's2', baseline=[1.0, 1.0], median=3.0,
                        method=None, first=False)
    reduce.first_signal = first
    np.testing.assert_allclose(reduce.get_sample_transmission(), [1.5, 1.5])


def test_baseline_ignores_positive_bursts(tmp_path):
    parent = make_parent(tmp_path)
    n = 1200
    frames = np.arange(n)
    truth = 1000.0 * (1.5 - 0.4 * np.sin(np.pi * frames / n))
    partial = truth.copy()
    for center in (200, 650, 900):
        partial += 600.0 * np.exp(-0.5 * ((frames - center) / 20.0) ** 2)
    reduce = FakeReduce(parent, 's1', nframes=n)
    reduce.partial_frames = NXfield(partial, name='partial_frames')
    reduce.partial_frames.attrs['method'] = PARTIAL_METHOD
    transmission = reduce.calculate_transmission()
    signal = transmission.nxsignal
    median = NXReduce._transmission_median(signal)
    np.testing.assert_allclose(signal.nxvalue * median, truth, rtol=0.03)
    assert abs(np.median(signal.nxvalue) - 1.0) < 1e-12
    assert NXReduce._transmission_attr(signal, 'method') == PARTIAL_METHOD
    assert NXReduce._transmission_attr(signal, 'median_monitor') is None


def test_baseline_records_monitor_median(tmp_path):
    parent = make_parent(tmp_path)
    reduce = FakeReduce(parent, 's1', monitor='MCS2', nframes=300,
                        monitor_signal=np.full(300, 2.0))
    reduce.partial_frames = NXfield(np.full(300, 10.0), name='partial_frames')
    signal = reduce.calculate_transmission().nxsignal
    np.testing.assert_allclose(NXReduce._transmission_median(signal), 10.0)
    np.testing.assert_allclose(
        NXReduce._transmission_attr(signal, 'median_monitor'), 5.0)


def test_baseline_weight_is_passed_to_the_fit_and_recorded(tmp_path,
                                                          monkeypatch):
    weights = []

    def spy(y, knot_spacing, upper_weight):
        weights.append(upper_weight)
        return np.asarray(y, dtype=float)

    monkeypatch.setattr('nxrefine.nxreduce.robust_baseline', spy)
    parent = make_parent(tmp_path)
    for weight in (BASELINE_WEIGHT, 1.0):
        reduce = FakeReduce(parent, 's1', nframes=50, baseline_weight=weight)
        reduce.partial_frames = NXfield(np.full(50, 10.0),
                                        name='partial_frames')
        signal = reduce.calculate_transmission().nxsignal
        assert NXReduce._transmission_attr(signal, 'baseline_weight') == weight
    assert weights == [BASELINE_WEIGHT, 1.0]


class FakeSettings:
    """Stand-in that supplies the baseline_weight property with a setting."""

    baseline_weight = NXReduce.baseline_weight

    def __init__(self, value=None, explicit=None):
        self._baseline_weight = explicit
        self.value = value

    def get_parameter(self, name):
        return self.value


def test_baseline_weight_property():
    assert FakeSettings().baseline_weight == BASELINE_WEIGHT
    assert FakeSettings(value='').baseline_weight == BASELINE_WEIGHT
    assert FakeSettings(value=1.0).baseline_weight == 1.0
    assert FakeSettings(value='0.5').baseline_weight == 0.5
    assert FakeSettings(value=1.0, explicit=0.4).baseline_weight == 0.4
    settings = FakeSettings()
    settings.baseline_weight = 1
    assert settings.baseline_weight == 1.0


def test_write_transmission_replaces_only_the_transmission(tmp_path):
    parent = make_parent(tmp_path)
    reduce = FakeReduce(parent, 's1', nframes=300, baseline=np.ones(300),
                        median=1.0)
    frame_sums = reduce.entry['frame_sums']
    partial = NXfield(np.full(300, 10.0), name='partial_frames')
    partial.attrs['method'] = PARTIAL_METHOD
    frame_sums['summed_frames'] = NXdata(NXfield(np.arange(300.0),
                                                 name='summed_frames'))
    frame_sums['summed_frames/partial_frames'] = partial
    summed = frame_sums['summed_frames/summed_frames'].nxvalue.copy()
    reduce.write_transmission()
    signal = reduce.entry['frame_sums/transmission'].nxsignal
    np.testing.assert_allclose(NXReduce._transmission_median(signal), 10.0)
    np.testing.assert_allclose(signal.nxvalue, 1.0)
    np.testing.assert_allclose(
        reduce.entry['frame_sums/summed_frames/summed_frames'].nxvalue,
        summed)
    assert reduce.consolidated == ['transmission']
    assert parent.reference['reference_scan'] == 's1'


def test_write_transmission_needs_partial_frames(tmp_path):
    reduce = FakeReduce(make_parent(tmp_path), 's1', nframes=10)
    with pytest.raises(NeXusError):
        reduce.write_transmission()
