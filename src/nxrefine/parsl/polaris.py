# -----------------------------------------------------------------------------
# Copyright (c) 2018-2026, Argonne National Laboratory.
#
# Distributed under the terms of an Open Source License.
#
# The full license is in the file LICENSE.pdf, distributed with this software.
# -----------------------------------------------------------------------------

"""Parsl configuration for Polaris at the ALCF.

Select it by setting the following in the `[parsl]` section of the
server settings, where `account` is the project the jobs are charged
against::

    config = nxrefine.parsl.polaris
    account = YourProject

To adapt it for another PBS Pro cluster, copy this file into the server
directory and set `config` to its name there. See `nxrefine.parsl.pbs`
for documentation of the `pbs_executor` helper this wraps.

Polaris runs PBS Pro. Its queue policies determine the shape of the two
executors declared below.

===============  =======  ============  ==================================
Queue            Nodes    Walltime      Limits
===============  =======  ============  ==================================
debug            1-2      <= 1 h        24 nodes in the queue
debug-scaling    1-10     <= 1 h        1 job per user
prod (routing)   10-496   3/6/24 h      by size: 10-24 -> 3 h, 25-99 ->
                                        6 h, 100-496 -> 24 h
preemptable      1-10     <= 72 h       20 jobs per project, killable
capacity         1-4      <= 168 h      1 job running per user
===============  =======  ============  ==================================

Small batches go to `capacity`, which is capped at 4 nodes and allows
one running job per user, hence `max_blocks=1`. Larger batches go to
`prod`, whose 10-node minimum sets the block size; `max_blocks` must be
at least `ntasks / large_nodes` or the tasks that do not fit will wait
for a free worker and may exceed the 3 hour walltime of the 10-24 node
tier.

Each node has 32 cores with 2 hardware threads each and 4 A100 GPUs.
NXRefine uses no GPU code, and one `nxreduce` process already fills a
node, so one worker per node is requested with all 64 threads visible
to it. This is deliberately not the four-workers-per-GPU arrangement in
the ALCF sample configuration.

Two Polaris requirements are handled here rather than left to settings:
jobs must declare the filesystems they use, and Parsl needs `TMPDIR`
pointed at a short path to avoid `AF_UNIX path too long`.
"""

from . import (LARGE, SMALL, get_config as _default_config,  # noqa: F401
               monitoring_hub, option, select_executor)  # noqa: F401
from .pbs import MPIEXEC_OVERRIDES, pbs_executor  # noqa: F401

TMPDIR = 'export TMPDIR=/tmp'


def worker_init(options):
    """Return the shell commands run on each node before the workers.

    The `worker_init` setting is appended, so it can activate the
    environment and re-export anything the login node had set, notably
    `NX_SERVER` and `NX_LOCKDIRECTORY`.
    """
    commands = [TMPDIR]
    setting = option(options, 'worker_init')
    if setting:
        commands.append(str(setting))
    return '; '.join(commands)


def polaris_executor(label, options, nodes, max_blocks, queue, walltime):
    """Return an executor backed by a Polaris PBS Pro allocation.

    Polaris requires `MpiExecLauncher` to start workers within a
    multi-node PBS allocation, a GPU declaration in the select directive,
    and `TMPDIR` set to a short path. These are all handled here on top
    of the generic `pbs_executor`.
    """
    from parsl.launchers import MpiExecLauncher
    polaris_options = dict(options)
    polaris_options['worker_init'] = worker_init(options)
    polaris_options['filesystems'] = option(options, 'filesystems',
                                            'home:eagle')
    polaris_options['cpus_per_node'] = 64
    return pbs_executor(
        label, polaris_options, nodes=nodes, max_blocks=max_blocks,
        queue=queue, walltime=walltime,
        launcher=MpiExecLauncher(bind_cmd='--cpu-bind',
                                 overrides=MPIEXEC_OVERRIDES),
        select_options='ngpus=4')


def get_config(options, run_dir):
    """Return the Parsl configuration for Polaris.

    Parameters
    ----------
    options : dict
        Settings from the `[parsl]` section, with `server_type` and
        `cores` added from the `[server]` section.
    run_dir : str or Path
        Directory for Parsl run logs and the monitoring database.
    """
    from pathlib import Path

    from parsl.config import Config

    if option(options, 'server_type') != 'multinode':
        return _default_config(options, run_dir)

    run_dir = Path(run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)

    return Config(
        executors=[
            polaris_executor(
                SMALL, options,
                nodes=min(int(option(options, 'small_nodes', 2)), 4),
                max_blocks=1,
                queue=option(options, 'small_queue', 'capacity'),
                walltime=str(option(options, 'small_walltime', '24:00:00'))),
            polaris_executor(
                LARGE, options,
                nodes=max(int(option(options, 'large_nodes', 10)), 10),
                max_blocks=int(option(options, 'max_blocks', 10)),
                queue=option(options, 'large_queue', 'prod'),
                walltime=str(option(options, 'walltime', '3:00:00'))),
        ],
        monitoring=monitoring_hub(options, local=False),
        run_dir=str(run_dir),
        app_cache=False,
        retries=int(option(options, 'retries', 0)),
    )
