# -----------------------------------------------------------------------------
# Copyright (c) 2018-2026, Argonne National Laboratory.
#
# Distributed under the terms of an Open Source License.
#
# The full license is in the file LICENSE.pdf, distributed with this software.
# -----------------------------------------------------------------------------

"""Parsl configuration for the NXRefine workflow server.

`NXServer` dispatches every task through Parsl. The Parsl `Config` is
supplied by a pair of functions:

    get_config(options, run_dir)        -> parsl.config.Config
    select_executor(options, ntasks)    -> executor label

`options` is a dictionary of the `[parsl]` section of the server
settings, with `server_type` and `cores` added from the `[server]`
section. `get_config` declares one labelled executor for each way a
batch might be run, and `select_executor` chooses between them for a
batch of `ntasks` commands.

The defaults below cover the `direct` and `multicore` server types and
a generic PBS Pro cluster. Sites whose scheduler needs more than the
`[parsl]` settings express should supply their own module and name it
in the `config` setting; see `nxrefine.nxparsl_polaris` for a worked
example. Executors are declared with no initial blocks, so declaring
one that a given batch does not use costs nothing.

Task memoisation is deliberately left off. Parsl memoises on the
command string, which would silently skip a command resubmitted after
an upstream fix; the `nxXXX` scripts already skip completed tasks based
on the workflow record in the wrapper file, which is both persistent
and aware of what was actually computed.
"""

import importlib
import importlib.util
import sys
from pathlib import Path

from nexusformat.nexus import NeXusError

LOCAL = 'nx-local'
SMALL = 'nx-small'
LARGE = 'nx-large'

MPIEXEC_OVERRIDES = '--depth=64 --ppn 1'


def option(options, key, default=None):
    """Return a setting, substituting `default` when it is unset.

    Parameters
    ----------
    options : dict
        Settings from the `[parsl]` section.
    key : str
        Name of the setting.
    default : optional
        Value to use when the setting is absent or blank.
    """
    value = options.get(key)
    return default if value is None else value


def monitoring_hub(options, local):
    """Return a MonitoringHub, or None if monitoring is disabled.

    Workers on other nodes report back over the network, so the hub
    needs an address they can reach. That is taken from the
    `hub_address` setting if it is defined, otherwise from the host
    name. Monitoring is disabled rather than misconfigured if the host
    name cannot be resolved, since it is not worth failing a run for.

    It is also disabled for the `direct` server type, where commands
    run in the user's own process and the hub's separate process would
    be started from within the GUI.

    Parameters
    ----------
    options : dict
        Settings from the `[parsl]` section.
    local : bool
        True if the workers run on this machine, in which case the hub
        only needs to be reachable over the loopback interface.
    """
    if not option(options, 'monitoring', True):
        return None
    if option(options, 'server_type') == 'direct':
        return None
    from parsl.monitoring import MonitoringHub
    address = option(options, 'hub_address')
    if address is None:
        if local:
            address = '127.0.0.1'
        else:
            from parsl.addresses import address_by_hostname
            try:
                address = address_by_hostname()
            except Exception:
                return None
    return MonitoringHub(
        hub_address=str(address),
        monitoring_debug=False,
        resource_monitoring_interval=30)


def scheduler_options(options):
    """Return the `#PBS` directives prepended to the submit script."""
    directives = []
    filesystems = option(options, 'filesystems')
    if filesystems:
        directives.append(f"#PBS -l filesystems={filesystems}")
    directives.append('#PBS -r y')
    return '\n'.join(directives)


def pbs_executor(label, options, nodes, max_blocks, queue, walltime,
                 launcher=None, select_options=''):
    """Return a HighThroughputExecutor backed by a PBS Pro allocation.

    One worker is started per node. A single `nxreduce` process already
    fills a node - `NXReduce.process_count` is half the hardware thread
    count - so packing more than one task onto a node would oversubscribe
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
        Launcher used to start workers within the allocation.
    select_options : str, optional
        Text appended to the `#PBS -l select` line.
    """
    from parsl.executors import HighThroughputExecutor
    from parsl.launchers import SingleNodeLauncher
    from parsl.providers import PBSProProvider

    if launcher is None:
        launcher = SingleNodeLauncher()
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
        worker_init=option(options, 'worker_init', ''),
        launcher=launcher,
    )
    return HighThroughputExecutor(
        label=label,
        max_workers_per_node=1,
        cpu_affinity='none',
        provider=provider,
    )


def local_executor(options):
    """Return an executor that runs tasks on this machine."""
    from parsl.executors import HighThroughputExecutor, ThreadPoolExecutor
    from parsl.providers import LocalProvider

    cores = int(option(options, 'cores', 1))
    if option(options, 'server_type') == 'direct':
        return ThreadPoolExecutor(label=LOCAL, max_threads=cores)
    return HighThroughputExecutor(
        label=LOCAL,
        max_workers_per_node=cores,
        cpu_affinity='none',
        provider=LocalProvider(init_blocks=0, min_blocks=0, max_blocks=1),
    )


def get_config(options, run_dir):
    """Return the Parsl configuration for the current server type.

    Parameters
    ----------
    options : dict
        Settings from the `[parsl]` section, with `server_type` and
        `cores` added from the `[server]` section.
    run_dir : str or Path
        Directory for Parsl run logs and the monitoring database.
    """
    from parsl.config import Config

    run_dir = Path(run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)
    local = option(options, 'server_type') != 'multinode'

    if local:
        executors = [local_executor(options)]
    else:
        walltime = str(option(options, 'walltime', '3:00:00'))
        executors = [
            pbs_executor(SMALL, options,
                         nodes=int(option(options, 'small_nodes', 1)),
                         max_blocks=1,
                         queue=option(options, 'small_queue', 'debug'),
                         walltime=walltime),
            pbs_executor(LARGE, options,
                         nodes=int(option(options, 'large_nodes', 10)),
                         max_blocks=int(option(options, 'max_blocks', 10)),
                         queue=option(options, 'large_queue', 'prod'),
                         walltime=walltime),
        ]

    return Config(
        executors=executors,
        monitoring=monitoring_hub(options, local),
        run_dir=str(run_dir),
        app_cache=False,
        retries=int(option(options, 'retries', 0)),
    )


def select_executor(options, ntasks):
    """Return the label of the executor a batch should be run on.

    Parameters
    ----------
    options : dict
        Settings from the `[parsl]` section.
    ntasks : int
        Number of commands in the batch.
    """
    if option(options, 'server_type') != 'multinode':
        return LOCAL
    threshold = int(option(options, 'batch_threshold', 4))
    return SMALL if ntasks <= threshold else LARGE


def import_config(config, directory):
    """Import the module providing the Parsl configuration functions.

    The `config` setting may name a Python file, either absolute or
    relative to the server directory, or an importable module. When it
    is unset, this module's own defaults are used.

    Parameters
    ----------
    config : str or None
        Value of the `config` setting in the `[parsl]` section.
    directory : str or Path
        Server directory, used to resolve a relative file name.

    Returns
    -------
    module
        A module defining `get_config` and `select_executor`.
    """
    if not config:
        return sys.modules[__name__]
    config = str(config)
    if config.endswith('.py') or '/' in config:
        path = Path(config).expanduser()
        if not path.is_absolute():
            path = Path(directory) / path
        if not path.exists():
            raise NeXusError(f"Parsl configuration '{path}' does not exist")
        spec = importlib.util.spec_from_file_location(path.stem, path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    else:
        module = importlib.import_module(config)
    for function in ['get_config', 'select_executor']:
        if not hasattr(module, function):
            raise NeXusError(
                f"Parsl configuration '{config}' has no '{function}' function")
    return module
