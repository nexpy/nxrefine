# -----------------------------------------------------------------------------
# Copyright (c) 2018-2026, Argonne National Laboratory.
#
# Distributed under the terms of an Open Source License.
#
# The full license is in the file LICENSE.pdf, distributed with this software.
# -----------------------------------------------------------------------------

"""Parsl executor helpers for PBS Pro clusters.

These helpers wrap Parsl's `PBSProProvider` with the conventions used by
NXRefine: one `nxreduce` worker per node, no initial blocks, and the
`#PBS -r y` rerun flag. They are used by the built-in `get_config`
default in `nxrefine.parsl` and by the Polaris site module
(`nxrefine.parsl.polaris`).

Sites running a PBS Pro cluster that does not need the Polaris-specific
launcher or GPU select options can use `pbs_executor` directly by
supplying a `config` module that imports it::

    from nxrefine.parsl.pbs import pbs_executor
    from nxrefine.parsl import SMALL, LARGE, option, monitoring_hub

    def get_config(options, run_dir):
        ...
        return Config(
            executors=[
                pbs_executor(SMALL, options, nodes=1, ...),
                pbs_executor(LARGE, options, nodes=8, ...),
            ],
            monitoring=monitoring_hub(options, local=False),
            ...
        )
"""

from . import init_commands, option

MPIEXEC_OVERRIDES = '--depth=64 --ppn 1'


def scheduler_options(options):
    """Return the `#PBS` directives prepended to the submit script.

    Parameters
    ----------
    options : dict
        Settings from the `[parsl]` section.
    """
    directives = []
    filesystems = option(options, 'filesystems')
    if filesystems:
        directives.append(f"#PBS -l filesystems={filesystems}")
    directives.append('#PBS -r y')
    return '\n'.join(directives)


def pbs_executor(label, options, nodes, max_blocks, queue, walltime,
                 launcher=None, select_options='', worker_init=None):
    """Return a HighThroughputExecutor backed by a PBS Pro allocation.

    One worker is started per node. A single `nxreduce` process already
    fills a node — `NXReduce.process_count` is half the hardware thread
    count — so packing more than one task onto a node would oversubscribe
    it.

    Parameters
    ----------
    label : str
        Executor label, used to route batches to this allocation.
    options : dict
        Settings from the `[parsl]` section.
    nodes : int
        Nodes requested per block. Each block is one `qsub`.
    max_blocks : int
        Maximum number of concurrent blocks. This must be at least
        `ntasks / nodes` or the tasks that do not fit will wait for a
        free worker and may exceed the block walltime.
    queue : str
        Scheduler queue to submit to.
    walltime : str
        Walltime requested per block, as `HH:MM:SS`.
    launcher : parsl.launchers.base.Launcher, optional
        Launcher used to start workers within the allocation. Defaults to
        `SingleNodeLauncher`, which is appropriate for most PBS clusters.
        Sites requiring `MpiExecLauncher` (such as Polaris) should pass
        it explicitly; see `nxrefine.parsl.polaris` for an example.
    select_options : str, optional
        Text appended to the `#PBS -l select` line, for example
        ``'ngpus=4'`` on systems that require GPU declarations.
    worker_init : str, optional
        Commands run in the batch job before the workers. Defaults to
        sourcing the script named by the `worker_init` setting. A site
        module adding commands of its own passes the whole string here
        rather than writing it back into `options`, where it would be
        read a second time as if it were still a file name.
    """
    from parsl.executors import HighThroughputExecutor
    from parsl.launchers import SingleNodeLauncher
    from parsl.providers import PBSProProvider

    if launcher is None:
        launcher = SingleNodeLauncher()
    if worker_init is None:
        worker_init = '; '.join(init_commands(options))
    provider = PBSProProvider(
        account=option(options, 'account'),
        queue=queue,
        walltime=walltime,
        nodes_per_block=nodes,
        cpus_per_node=int(option(options, 'cpus_per_node', 64)),
        init_blocks=0,
        min_blocks=0,
        max_blocks=max_blocks,
        parallelism=1,
        scheduler_options=scheduler_options(options),
        select_options=select_options,
        worker_init=worker_init,
        launcher=launcher,
    )
    return HighThroughputExecutor(
        label=label,
        max_workers_per_node=1,
        cpu_affinity='none',
        provider=provider,
    )
