# -----------------------------------------------------------------------------
# Copyright (c) 2026, Argonne National Laboratory.
#
# Distributed under the terms of an Open Source License.
#
# The full license is in the file LICENSE.pdf, distributed with this software.
# -----------------------------------------------------------------------------
"""Shared helpers for the dialogs that operate on scan files."""

from nexpy.gui.utils import display_message

from nxrefine.nxparent import NXParent
from nxrefine.nxreduce import NXReduce


def select_parent(dialog):
    """Redirect a dialog's selection to the parent of a registered scan.

    A scan that belongs to a parent is edited through that parent, so
    that its settings stay consistent with the other scans.

    Parameters
    ----------
    dialog : NXDialog
        The dialog whose ``parent``, ``parent_file`` and file box are to
        be redirected.
    """
    parent_file = dialog.parent.parent_file
    if parent_file is None or not parent_file.is_file():
        return
    scan_name = dialog.parent_file.name
    dialog.parent_file = parent_file
    dialog.parent = NXParent(parent_file)
    dialog.filename.setText(str(parent_file))
    display_message(
        f"'{scan_name}' has a parent file",
        f"'{parent_file.name}' has been selected instead. To edit "
        f"'{scan_name}' separately, remove it from the parent's "
        "selected files.")


def add_parent_subentries(dialog):
    """Add parent-file subentries to a dialog's entry dropdown.

    Reads the NXsubentry names from ``/entry`` of the parent scans file
    and inserts ``entry_name/subentry_name`` paths into ``entry_box`` for
    each top-level entry that does not already have them listed.

    This is called from ``switch_root`` overrides in dialogs that need to
    expose subentries defined in the parent ``*_scans.nxs`` file even
    when those subentries have not yet been created in the individual scan
    file.

    Parameters
    ----------
    dialog : NXDialog
        The dialog whose ``entry_box`` is to be updated.
    """
    try:
        top_entries = [item for item in dialog.entry_box.items()
                       if '/' not in item]
        if not top_entries:
            return
        first_entry = dialog.tree[
            f"{dialog.root_box.selected}/{top_entries[0]}"]
        reduce = NXReduce(first_entry)
        if not reduce.parent:
            return
        parent_sub_names = [
            s.nxname for s in reduce.parent.root['entry'].NXsubentry]
        for entry_name in top_entries:
            for sub_name in parent_sub_names:
                path = f"{entry_name}/{sub_name}"
                if path not in dialog.entry_box:
                    existing_subs = [
                        item for item in dialog.entry_box.items()
                        if item.startswith(f"{entry_name}/")]
                    insert_at = (dialog.entry_box.findText(entry_name)
                                 + 1 + len(existing_subs))
                    dialog.entry_box.insert(insert_at, path)
    except Exception:
        pass


def hide_combined_entry(dialog):
    """Remove the combined ``/entry`` group from a dialog's entry dropdown.

    The top-level ``/entry`` group in a wrapper file is a merged view
    that holds combined transforms and PDFs; it has no raw detector
    data and frequently lacks per-scan geometry such as
    ``instrument/detector/beam_center_x``/``beam_center_y``. Per-scan
    reduction dialogs (Find Maximum, Find Peaks, Refine Lattice,
    Prepare 3D Mask) must therefore operate on the individual scan
    entries (``f1``, ``f2``, …) rather than ``/entry``. Hiding it from
    the dropdown prevents the user from picking an entry the dialog
    cannot work with.

    All items whose path starts with ``entry`` (i.e. the bare ``entry``
    top-level entry and any ``entry/subentry`` paths) are removed. If
    the currently selected item is one of those, the first remaining
    entry is selected instead.

    Parameters
    ----------
    dialog : NXDialog
        The dialog whose ``entry_box`` is to be updated.
    """
    to_remove = [item for item in dialog.entry_box.items()
                 if item == 'entry' or item.startswith('entry/')]
    was_selected = dialog.entry_box.selected in to_remove
    for item in to_remove:
        dialog.entry_box.remove(item)
    if was_selected and dialog.entry_box.count() > 0:
        dialog.entry_box.setCurrentIndex(0)
