# -----------------------------------------------------------------------------
# Copyright (c) 2018-2026, Argonne National Laboratory.
#
# Distributed under the terms of an Open Source License.
#
# The full license is in the file LICENSE.pdf, distributed with this software.
# -----------------------------------------------------------------------------

"""Parsl executor helpers for SGE (Sun/Son of/Univa Grid Engine) clusters.

These helpers wrap Parsl's `GridEngineProvider` with the conventions used by
NXRefine: one `nxreduce` worker per job, no initial blocks, and parallel-
environment slot declarations built from the `[parsl]` settings.

This module is a low-level helper, analogous to `nxrefine.parsl.pbs`. It is
**not** directly usable as the `config =` value in settings — it has no
`get_config` or `select_executor`. Site modules import it and supply those
functions with site-appropriate defaults::

    from nxrefine.parsl.sge import sge_executor, scheduler_options
    from nxrefine.parsl import SMALL, LARGE, option, monitoring_hub

    def get_config(options, run_dir):
        walltime = str(option(options, 'walltime', '48:00:00'))
        executors = [
            sge_executor(SMALL, options, max_blocks=1,
                         queue=option(options, 'small_queue', 'all.q'),
                         walltime=walltime),
            sge_executor(LARGE, options,
                         max_blocks=int(option(options, 'max_blocks', 10)),
                         queue=option(options, 'large_queue', 'all.q'),
                         walltime=walltime),
        ]
        ...

Key SGE concepts vs PBS
-----------------------
PBS allocates whole nodes; worker parallelism is expressed as ``cpus_per_node``.
SGE allocates *slots* (logical CPU units). Multi-threaded single-node jobs
request slots via a parallel environment (``-pe <name> <slots>``). For NXRefine
the slot count therefore plays the role of ``cpus_per_node`` and is read from
that same setting.

The ``GridEngineProvider`` template already emits::

    #$ -l h_rt=${walltime}
    #$ -cwd
    #$ -S /bin/bash
    #$ -o / -e  (stdout / stderr)

so only the PE declaration and any optional resource flags need to be added via
the ``scheduler_options`` parameter.
"""

from . import init_commands, option


def scheduler_options(options):
    """Return the ``#$`` directives prepended to the SGE submit script.

    Parameters
    ----------
    options : dict
        Settings from the ``[parsl]`` section.

    Returns
    -------
    str
        Newline-separated ``#$ -...`` directives, or an empty string when no
        optional directives are needed.

    Notes
    -----
    ``pe`` sets the SGE parallel-environment name (e.g. ``sge_pe`` at CLASSE).
    When ``pe`` is given, the slot count comes from ``cpus_per_node`` (default
    1, meaning no slot request — sites should set an explicit value).  The PE
    declaration is omitted entirely when ``pe`` is absent or blank, allowing the
    scheduler to apply its own default slot policy.

    ``mem_free`` adds a ``-l mem_free=<value>`` resource request (e.g. ``8G``).
    """
    directives = []
    pe = option(options, 'pe')
    if pe:
        slots = int(option(options, 'cpus_per_node', 1))
        directives.append(f'#$ -pe {pe} {slots}')
    mem_free = option(options, 'mem_free')
    if mem_free:
        directives.append(f'#$ -l mem_free={mem_free}')
    return '\n'.join(directives)


def sge_executor(label, options, max_blocks, queue, walltime):
    """Return a HighThroughputExecutor backed by an SGE allocation.

    One worker is started per submitted job. A single ``nxreduce`` process
    already fills a node — ``NXReduce.process_count`` is half the hardware
    thread count — so requesting more than one Parsl worker per job would
    oversubscribe the node.

    Parameters
    ----------
    label : str
        Executor label, used to route batches to this allocation.
    options : dict
        Settings from the ``[parsl]`` section.
    max_blocks : int
        Maximum number of concurrently submitted SGE jobs (blocks). Each block
        is one ``qsub``.  This must be at least the number of parallel tasks
        expected, or excess tasks will wait for a free worker.
    queue : str
        SGE queue to submit to (``-q`` flag).  Pass ``None`` to omit the flag
        and let the scheduler choose.
    walltime : str
        Wall-clock time limit per job, as ``HH:MM:SS``.
    """
    from parsl.executors import HighThroughputExecutor
    from parsl.providers import GridEngineProvider

    provider = GridEngineProvider(
        nodes_per_block=1,
        init_blocks=0,
        min_blocks=0,
        max_blocks=max_blocks,
        parallelism=1,
        walltime=walltime,
        queue=queue,
        scheduler_options=scheduler_options(options),
        worker_init='; '.join(init_commands(options)),
    )
    return HighThroughputExecutor(
        label=label,
        max_workers_per_node=1,
        cpu_affinity='none',
        provider=provider,
    )
