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
    worker_init = polaris_setup.sh
    walltime = 3:00:00

`walltime` is shared by both executors below rather than set
separately for each, since on a busy `capacity` queue a shorter
walltime has been found to get jobs running sooner than a longer one,
and the same applies on `prod`. It defaults to 3 hours when unset.

`worker_init` names a shell script in the server directory, sourced in
the batch job to recreate the environment that the compute nodes do not
inherit from the login node: the module loads, the conda environment,
and `NX_SERVER` and `NX_LOCKDIRECTORY`. `polaris_setup.sh`, beside this
module, is an annotated example to copy there and edit.

The script must be on a filesystem named in the `filesystems` setting,
which defaults to `home:eagle`.

To adapt it for another PBS Pro cluster, copy this file into the server
directory and set `config` to its name there. See `nxrefine.parsl.pbs`
for documentation of the `pbs_executor` helper this wraps.

Polaris runs PBS Pro. Its queue policies determine the shape of the two
executors declared below.

==============  ======  ========  =============================================
Queue           Nodes   Walltime  Limits
==============  ======  ========  =============================================
debug           1-2     <= 1 h    24 nodes in use by the queue
debug-scaling   1-10    <= 1 h    1 job per user
prod (routing)  10-496  3/6/24 h  by size: 10-24 -> 3 h, 25-99 -> 6 h,
                                  100-496 -> 24 h; 10 running and 100 queued
                                  per project
preemptable     1-10    <= 72 h   20 jobs per project, killable
capacity        1-4     <= 168 h  1 running and 2 queued per user, 32 nodes
                                  across all jobs
==============  ======  ========  =============================================

Small batches go to `capacity`, which is capped at 4 nodes and allows
one running job per user, hence `max_blocks=1`. Larger batches go to
`prod`, whose 10-node minimum is the smallest block, set by
`large_nodes`.

One worker runs per node, so a block runs one command on each of its
nodes. A batch is run in a block with a node for every command, so that
it is one job in the queue rather than several that each have to wait,
and no node is requested that has no command to run, except to reach the
10-node minimum. The block is no larger than `max_large_nodes`, which
defaults to 24, the largest block in the 3 hour tier. A batch needing
more is divided evenly among the fewest blocks that hold it: 12 commands
run in one 12-node job and 30 in two 15-node jobs. The executors for
blocks that are larger than `large_nodes` are added when a batch needs
them, and all of them share `max_blocks`. Set `max_large_nodes` equal to
`large_nodes` to run every batch in blocks of that size.

`max_blocks` is the number of jobs the executor may run at once. Too low
and the surplus commands wait for a free worker, which risks the 3 hour
walltime of the 10-24 node tier; too high and one user's batches take
all ten of the running jobs the whole project is allowed.

Each node has 32 cores with 2 hardware threads each and 4 A100 GPUs.
NXRefine uses no GPU code, and one `nxreduce` process already fills a
node, so one worker per node is requested with all 64 threads visible
to it. This is deliberately not the four-workers-per-GPU arrangement in
the ALCF sample configuration.

Three Polaris requirements are handled here rather than left to
settings: jobs must declare the filesystems they use, Parsl needs
`TMPDIR` pointed at a short path to avoid `AF_UNIX path too long`, and
OpenBLAS has to be held to one thread per process so that the worker
processes a task starts do not exhaust the limit on tasks between them.
"""

from . import (LARGE, SMALL, choose_executor,  # noqa: F401
               get_config as _default_config, init_commands, label_nodes,
               monitoring_hub, option)
from .pbs import MPIEXEC_OVERRIDES, pbs_executor  # noqa: F401

TMPDIR = 'export TMPDIR=/tmp'
OPENBLAS = 'export OPENBLAS_NUM_THREADS=1'
PROD_MINIMUM = 10
PROD_SMALL_MAXIMUM = 24


def worker_commands(options):
    """Return the shell commands run on each node before the workers.

    `TMPDIR` is pointed at a short path and OpenBLAS is held to one
    thread per process. A task runs `NXExecutor` with a worker process
    for every two hardware threads, and each of those would otherwise
    start a thread per core, which exhausts the limit on tasks before
    any of them can import NumPy.

    The script named by the `worker_init` setting is sourced afterwards,
    so it can activate the environment and re-export anything the login
    node had set, notably `NX_SERVER` and `NX_LOCKDIRECTORY`, and can
    raise either limit again if a task ever needs it.
    """
    return '; '.join([TMPDIR, OPENBLAS] + init_commands(options))


def polaris_executor(label, options, nodes, max_blocks, queue, walltime):
    """Return an executor backed by a Polaris PBS Pro allocation.

    Polaris requires `MpiExecLauncher` to start workers within a
    multi-node PBS allocation, a GPU declaration in the select directive,
    and `TMPDIR` set to a short path. These are all handled here on top
    of the generic `pbs_executor`.
    """
    from parsl.launchers import MpiExecLauncher
    polaris_options = dict(options)
    polaris_options['filesystems'] = option(options, 'filesystems',
                                            'home:eagle')
    polaris_options['cpus_per_node'] = 64
    return pbs_executor(
        label, polaris_options, nodes=nodes, max_blocks=max_blocks,
        queue=queue, walltime=walltime,
        launcher=MpiExecLauncher(bind_cmd='--cpu-bind',
                                 overrides=MPIEXEC_OVERRIDES),
        select_options='ngpus=4',
        worker_init=worker_commands(options))


def node_range(options):
    """Return the smallest and largest block size of the large executor.

    The smallest is the `large_nodes` setting, which cannot be below the
    10-node minimum of the `prod` queue. The largest is the
    `max_large_nodes` setting, by default the 24 nodes at which `prod`
    changes to a longer walltime tier, and no smaller than the smallest.

    Parameters
    ----------
    options : dict
        Settings from the `[parsl]` section.
    """
    minimum = max(int(option(options, 'large_nodes', PROD_MINIMUM)),
                  PROD_MINIMUM)
    maximum = int(option(options, 'max_large_nodes', PROD_SMALL_MAXIMUM))
    return minimum, max(maximum, minimum)


def select_executor(options, ntasks):
    """Return the label of the executor a batch should be run on.

    A batch of more than `batch_threshold` commands goes to `prod` in
    one block with a node for each command, at least 10 and at most
    `max_large_nodes` nodes, or in the fewest blocks of that size that
    hold it.

    Parameters
    ----------
    options : dict
        Settings from the `[parsl]` section.
    ntasks : int
        Number of commands in the batch.
    """
    return choose_executor(options, ntasks, node_range(options))


def large_executor(options, label):
    """Return the `prod` executor with the block size named by `label`.

    The server calls this when `select_executor` returns the label of an
    executor with larger blocks than the one declared by `get_config`.

    Parameters
    ----------
    options : dict
        Settings from the `[parsl]` section.
    label : str
        Executor label made by `nxrefine.parsl.large_label`.

    Returns
    -------
    HighThroughputExecutor or None
        The executor, or None if the label does not name a block size.
    """
    nodes = label_nodes(label)
    if nodes is None:
        return None
    return polaris_executor(
        label, options, nodes=nodes,
        max_blocks=int(option(options, 'max_blocks', 10)),
        queue=option(options, 'large_queue', 'prod'),
        walltime=str(option(options, 'walltime', '3:00:00')))


def get_config(options, run_dir):
    """Return the Parsl configuration for Polaris.

    Parameters
    ----------
    options : dict
        Settings from the `[parsl]` section, with `server_type`, `cores`
        and the server `directory` added by the server.
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
                walltime=str(option(options, 'walltime', '3:00:00'))),
            polaris_executor(
                LARGE, options,
                nodes=node_range(options)[0],
                max_blocks=int(option(options, 'max_blocks', 10)),
                queue=option(options, 'large_queue', 'prod'),
                walltime=str(option(options, 'walltime', '3:00:00'))),
        ],
        monitoring=monitoring_hub(options, local=False),
        run_dir=str(run_dir),
        retries=int(option(options, 'retries', 0)),
    )
