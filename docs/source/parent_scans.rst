Parent Files and the Scan Registry
**********************************
This page documents how *NXRefine* relates a *parent* file to the individual
*scan* files it groups together, the on-disk data model that records the
relationship, and the classes and dialogs that read and write it. It is aimed
at developers extending the reduction workflow.

Overview
========
A single experiment is organised around a **parent file**, named
``{sample}_scans.nxs``, which holds the shared geometry, reduction settings,
and a registry of the scans that belong to it. Each **scan file** is an
individual rotation dataset (for example one temperature point) that records
which parent it belongs to.

The relationship is *bidirectional by convention*:

- the **parent lists each scan** in ``/entry/nxscans/scans`` (with a parallel
  ``selected`` flag), and
- each **scan names its parent** in its own ``/entry/nxscans/parent`` field.

``NXParent.is_parent`` verifies that the two agree. Keeping both sides
consistent is the responsibility of the code that creates scans
(``NXParent.add_scan``) and of the reconciliation paths described in
`Reconciling a copied parent`_.

The ``nxscans`` data model
==========================
``nxscans`` is an ``NXprocess`` group that lives in the **parent** file at
``/entry/nxscans`` (or ``/entry/{subentry}/nxscans`` when a subentry is
active). It is the central registry of the scan collection and contains:

``scans``
    A resizable 1-D string field (``string_dtype``, ``maxshape=(None,)``).
    Each element is a scan file **stem** (the filename without ``.nxs``),
    e.g. ``sample1_300K``.

``selected``
    A resizable 1-D ``bool`` field, index-aligned with ``scans``. Only the
    selected scans feed downstream consolidation and reduction.

``settings``
    An ``NXparameters`` group of reduction parameters shared by all scans
    (threshold, frame limits, monitor/normalisation, Q limits, mask
    parameters, ``scan_path``/``scan_units``, ...).

``transform``
    An optional ``NXdata`` group holding the output Q-grid axes (Qh/Qk/Ql).

``description``
    An optional ``NXnote`` describing a subentry.

Note that the on-disk field is named ``scans``; ``scan_files`` is a *Python
property* on ``NXParent`` that resolves those stems to absolute ``Path``
objects — the two are not the same thing.

In a **scan** file, the same ``nxscans`` group instead holds a single
``parent`` field: the parent's file **name** (e.g. ``sample_scans.nxs``),
stored as a plain string, not a NeXus link. It is resolved relative to the
scan's own directory, which is what makes the reference survive a copy to
another disk.

The ``NXParent`` class
======================
``NXParent`` (``src/nxrefine/nxparent.py``) wraps a parent ``_scans.nxs``
file and is the single source of truth for the data model above. All of the
refine/experiment dialogs and ``NXReduce`` build on it.

Construction and entry selection
--------------------------------
``NXParent(filename, subentry=None)`` accepts a path, an ``NXroot``, or
``None``. The filename must end with ``_scans``. A ``subentry`` selects a
group within ``/entry``; when set, all accessors operate on
``/entry/{subentry}`` instead of ``/entry`` (see ``entry_path``,
``scan_entry``, ``scan_info``).

Key accessors
-------------
``scan_info``
    The active ``nxscans`` ``NXprocess`` group; ``settings`` and ``transform``
    return its like-named children.

``scans`` / ``selected``
    Sorted (``natural_sort``) lists of scan stems and their booleans;
    ``index(scan)`` gives the raw, unsorted position needed for in-place
    writes.

``scan_file(scan)`` / ``scan_files`` / ``selected_scans``
    Resolve a stem to an absolute ``.nxs`` path; the paths of all registered
    scans; and the paths of only the selected scans.

``other_scan_files``
    ``.nxs`` files in the directory that are neither registered scans nor
    ``*_scans`` parents.

``is_parent(scan)`` / ``has_parent(scan)``
    Whether a scan's ``parent`` back-pointer names *this* parent, and whether
    it records *any* parent.

Key mutators
------------
``initialize()``
    Builds the ``entry -> nxscans (scans, selected, settings)`` skeleton plus
    an ``NXsample``. The ``scans`` and ``selected`` fields are created empty.

``add_scan(scan, selected=True)``
    The central mutator. Resizes and appends to ``scans``/``selected`` (guarded
    against duplicates), then calls ``add_parent`` to stamp the scan's
    back-pointer, and migrates any legacy structure.

``add_parent(scan)``
    Writes ``{entry_path}/nxscans/parent = <parent filename>`` into the *scan*
    file.

``add_scans(selected=True)``
    Globs ``{sample}_*.nxs`` and adds each one (does not check ``is_parent``).

``sync_scans(selected=True)``
    Reconciles the registry from the scans' back-pointers — see
    `Reconciling a copied parent`_.

``update_scan_data()`` / ``create_scan_data()``
    Consolidate per-scan ``NXdata`` groups into the parent with
    ``nxconsolidate`` along ``scan_path``.

Dialogs
=======

The New Parent dialog
---------------------
``src/nxrefine/plugins/experiment/new_parent.py`` (``Experiment -> New
Parent``). A wizard that chooses the experiment directory, sample/label, and a
configuration file to copy geometry from, then edits reduction parameters.
``create_parent()`` calls ``NXParent.initialize()`` and ``copy_file(...)`` and
writes the parameters into ``nxscans/settings``. **The parent is created with
an empty scan list** — scans are added later.

The New Scan dialog
-------------------
``src/nxrefine/plugins/experiment/new_scan.py`` (``Experiment -> New Scan``).
``create_scan()`` clones the parent entries into a new per-value scan file,
repoints the raw-data links, writes the scan variable, then calls
``NXParent.add_scan(...)``. That single call is what appends the new scan to
the parent registry *and* stamps the back-pointer into the scan file.

The Initialize Scans and Select Files dialogs
---------------------------------------------
``src/nxrefine/plugins/refine/initialize_scans.py`` is a hub for a chosen
parent: pick/create a subentry, then open **Select Files**, **Edit Settings**,
**Define Lattice**, **Setup Transforms**, or **Copy NeXus File**.

**Select Files** (``select_files.py``, ``FilesDialog``) shows two checkbox
lists: the already-registered **Scan Files** (pre-checked per ``selected``)
and the unregistered **Other Files** (``other_scan_files``). On ``accept`` it
toggles ``selected`` in place for existing scans (by ``index``) and calls
``add_scan`` for newly chosen files, then consolidates data on a background
thread (``ScanDataWorker`` -> ``update_scan_data``).

``NXReduce`` and the parent
===========================
``NXReduce`` (``src/nxrefine/nxreduce.py``) is the reduction workflow
controller for a single scan entry (``NXMultiReduce`` handles the cross-entry
combine/PDF steps).

Parent resolution is lazy through three properties:

``parent_file``
    Reads ``entry/nxscans/parent`` from the scan's *own* wrapper file and
    resolves it against ``base_directory``; falls back to
    ``{sample}_scans.nxs`` when the field is absent.

``parent``
    Wraps ``parent_file`` as an ``NXParent`` (with the current subentry)
    when the file exists.

``parent_entry``
    The parent's ``NXentry`` matching the current entry name.

Reduction parameters are read from the parent's ``nxscans/settings``
(``get_parameter``) and written back there (``write_parameters`` ->
``NXParent.write_settings``); when no parent exists they fall back to the
wrapper's ``/entry/nxreduce`` for backward compatibility.

The workflow operations — ``nxload``, ``nxlink``, ``nxmax``, ``nxfind``,
``nxrefine``, ``nxprepare``, ``nxtransform``, ``nxsum`` (and
``NXMultiReduce.nxcombine`` / ``nxpdf``) — are dispatched by ``nxreduce()``
according to boolean flags. They all pass through ``record_start`` /
``record`` / ``record_end`` for status tracking, which makes ``record_start``
a convenient single choke point for per-run hooks.

Reconciling a copied parent
===========================
A parent is often created on one machine and copied to a second disk *before*
any scans are added, so the copy starts with an empty registry even though the
scan files (each carrying a ``parent`` back-pointer) are also copied over. Two
paths rebuild the registry from those back-pointers:

``NXParent.sync_scans()``
    Iterates ``other_scan_files`` and registers each file whose back-pointer
    matches this parent (``is_parent``) and that is not already listed. It is
    called from ``FilesDialog.__init__`` so **Select Files** shows the
    recovered scans pre-checked rather than under *Other Files*.

``NXReduce.register_with_parent()``
    Called once per instance from ``record_start``. When the scan reports a
    parent that does not yet list it, the scan adds itself via
    ``add_scan(..., selected=True)``. It is a no-op for scans with no recorded
    parent and for the parent file itself.

Because both paths funnel through ``add_scan`` (which is duplicate-guarded and
resizes under the file lock configured by ``nxsetconfig``), they are
idempotent. Concurrency between reduction jobs each registering themselves is
serialised by that same NeXus file locking.
