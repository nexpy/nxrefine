# -----------------------------------------------------------------------------
# Copyright (c) 2018-2026, Argonne National Laboratory.
#
# Distributed under the terms of an Open Source License.
#
# The full license is in the file LICENSE.pdf, distributed with this software.
# -----------------------------------------------------------------------------

"""Parsl configuration for the CLASSE Compute Farm at Cornell University.

Select it by setting the following in the ``[parsl]`` section of the server
settings::

    config = nxrefine.parsl.classe

To adapt it for another SGE cluster, copy this file into the server directory,
adjust the defaults (queue name, PE name, ``cpus_per_node``), and point
``config`` at the copy.  See ``nxrefine.parsl.sge`` for documentation of the
``sge_executor`` helper this wraps.

CLASSE Compute Farm overview
-----------------------------
The farm runs SGE (Grid Engine) and is accessed via ``qsub``.

=====================  =======================================================
Resource               Detail
=====================  =======================================================
Primary batch queue    ``all.q`` — all nodes, 48 h maximum walltime
Interactive queue      ``interactive.q`` — reserved for interactive sessions
Multi-thread PE        ``sge_pe`` — slots on a single node
Thread env vars        ``MKL_NUM_THREADS`` / ``OMP_NUM_THREADS`` must be set to
                       ``$NSLOTS`` to avoid accidental CPU over-subscription
Job limits             120 running / 1 000 queued per user
Default OS             AlmaLinux 9 (as of January 2025)
=====================  =======================================================

The SMALL executor accepts one running job at a time (``max_blocks=1``) and is
used for small batches.  The LARGE executor allows up to ``max_blocks``
concurrent jobs and handles larger batches.  Both target ``all.q``; use the
``small_queue`` / ``large_queue`` settings to override.

The default walltime is set to the CLASSE maximum of 48 hours so that jobs are
not aborted on busy systems.  Override with the ``walltime`` setting when a
shorter limit is preferred.

Set ``cpus_per_node`` in the ``[parsl]`` section to the number of SGE slots
needed for one ``nxreduce`` process on your CLASSE nodes (typically 32 for
current nodes).  The global default of 64 reflects Polaris, not CLASSE.
"""

from . import (LARGE, SMALL, get_config as _default_config,  # noqa: F401
               init_commands, monitoring_hub, option,  # noqa: F401
               select_executor)  # noqa: F401
from .sge import sge_executor  # noqa: F401

# CLASSE parallel-environment name for single-node multi-threaded jobs.
_PE = 'sge_pe'

# Shell commands that pin MKL and OpenMP to the slot count SGE granted.
_THREAD_EXPORTS = (
    'export MKL_NUM_THREADS=$NSLOTS; '
    'export OMP_NUM_THREADS=$NSLOTS'
)


def worker_init(options):
    """Return the shell commands run on each node before the workers start.

    MKL and OpenMP thread counts are pinned to ``$NSLOTS`` (the number of
    SGE slots granted) so that ``nxreduce`` does not accidentally spawn more
    threads than requested.  The script named by the ``worker_init`` setting
    is sourced after these exports, allowing it to activate a conda
    environment and re-export variables such as ``NX_SERVER`` and
    ``NX_LOCKDIRECTORY``.
    """
    return '; '.join([_THREAD_EXPORTS] + init_commands(options))


def classe_executor(label, options, max_blocks, queue, walltime):
    """Return an executor backed by a CLASSE SGE allocation.

    Injects the CLASSE parallel-environment name and the thread-pinning worker
    initialisation on top of the generic ``sge_executor``.

    Parameters
    ----------
    label : str
        Executor label used to route batches to this allocation.
    options : dict
        Settings from the ``[parsl]`` section.
    max_blocks : int
        Maximum number of concurrently submitted SGE jobs (blocks).
    queue : str
        SGE queue to target.
    walltime : str
        Wall-clock time limit per job, as ``HH:MM:SS``.
    """
    classe_options = dict(options)
    # Apply CLASSE PE default without overriding an explicit user setting.
    if not option(options, 'pe'):
        classe_options['pe'] = _PE
    classe_options['worker_init'] = worker_init(options)

    return sge_executor(label, classe_options,
                        max_blocks=max_blocks,
                        queue=queue,
                        walltime=walltime)


def get_config(options, run_dir):
    """Return the Parsl configuration for the CLASSE Compute Farm.

    Parameters
    ----------
    options : dict
        Settings from the ``[parsl]`` section, with ``server_type``,
        ``cores`` and the server ``directory`` added by the server.
    run_dir : str or pathlib.Path
        Directory for Parsl run logs and the monitoring database.
    """
    from pathlib import Path

    from parsl.config import Config

    if option(options, 'server_type') != 'multinode':
        return _default_config(options, run_dir)

    run_dir = Path(run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)

    walltime = str(option(options, 'walltime', '48:00:00'))
    return Config(
        executors=[
            classe_executor(
                SMALL, options,
                max_blocks=1,
                queue=option(options, 'small_queue', 'all.q'),
                walltime=walltime),
            classe_executor(
                LARGE, options,
                max_blocks=int(option(options, 'max_blocks', 10)),
                queue=option(options, 'large_queue', 'all.q'),
                walltime=walltime),
        ],
        monitoring=monitoring_hub(options, local=False),
        run_dir=str(run_dir),
        app_cache=False,
        retries=int(option(options, 'retries', 0)),
    )
