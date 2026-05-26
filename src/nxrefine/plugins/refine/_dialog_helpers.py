# -----------------------------------------------------------------------------
# Copyright (c) 2026, Argonne National Laboratory.
#
# Distributed under the terms of an Open Source License.
#
# The full license is in the file LICENSE.pdf, distributed with this software.
# -----------------------------------------------------------------------------
"""Shared helpers for the refine-menu dialogs."""


def hide_combined_entry(dialog):
    """Remove the combined ``/entry`` from a dialog's entry dropdown.

    The top-level ``/entry`` group in a wrapper file is a merged view
    that holds combined transforms and PDFs; it has no raw detector
    data and frequently lacks per-scan geometry such as
    ``instrument/detector/beam_center_x``/``beam_center_y``. Per-scan
    reduction dialogs (Find Maximum, Find Peaks, Refine Lattice,
    Prepare 3D Mask) must therefore operate on the individual scan
    entries (``f1``, ``f2``, …) rather than ``/entry``. Hiding it from
    the dropdown prevents the user from picking an entry the dialog
    cannot work with.

    If ``/entry`` was the currently selected item, the first remaining
    entry is selected instead.
    """
    if 'entry' in dialog.entry_box:
        was_selected = (dialog.entry_box.selected == 'entry')
        dialog.entry_box.remove('entry')
        if was_selected and dialog.entry_box.count() > 0:
            dialog.entry_box.setCurrentIndex(0)
