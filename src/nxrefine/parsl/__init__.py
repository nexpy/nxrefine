# -----------------------------------------------------------------------------
# Copyright (c) 2018-2026, Argonne National Laboratory.
#
# Distributed under the terms of an Open Source License.
#
# The full license is in the file LICENSE.pdf, distributed with this software.
# -----------------------------------------------------------------------------

"""Scheduler-neutral Parsl configuration for the NXRefine workflow server.

`NXServer` dispatches every task through Parsl. The Parsl `Config` is
supplied by a pair of functions:

    get_config(options, run_dir)        -> parsl.config.Config
    select_executor(options, ntasks)    -> executor label

`options` is a dictionary of the `[parsl]` section of the server
settings, with `server_type`, `cores` and the server `directory` added
by the server. `get_config` declares one labelled executor for each way a
batch might be run, and `select_executor` chooses between them for a
batch of `ntasks` commands.

The defaults below cover the `direct` and `multicore` server types and
provide a starting-point PBS Pro configuration for `multinode`. Sites
whose scheduler is not PBS Pro, or whose cluster has requirements beyond
what the `[parsl]` settings express, should supply their own module and
name it in the `config` setting:

    ; ALCF Polaris
    config = nxrefine.parsl.polaris
    ; CLASSE Compute Farm at Cornell (SGE)
    config = nxrefine.parsl.classe
    ; arbitrary site file
    config = /path/to/my_config.py

Compute nodes do not inherit the environment the server was started in,
so anything the tasks need — module loads, the conda environment, and
the `NX_SERVER` and `NX_LOCKDIRECTORY` variables — has to be set up
again within the batch job. The `worker_init` setting names a shell
script that is sourced there to do that:

    worker_init = polaris_setup.sh

The name is resolved relative to the server directory, the one holding
`settings.ini`, so the script normally sits beside it. An absolute path
is also accepted. See `init_commands` for what the script has to satisfy.

Scheduler-specific helpers live in sub-modules:

    nxrefine.parsl.pbs      PBS Pro (including Polaris at ALCF)
    nxrefine.parsl.sge      Generic SGE / Grid Engine clusters
    nxrefine.parsl.classe   CLASSE Compute Farm at Cornell (SGE)

Executors are declared with no initial blocks, so an unused executor
costs nothing. Task memoisation is deliberately left off — the `nxXXX`
scripts already skip completed tasks from the workflow record in the
wrapper file, which is both persistent and aware of what was actually
computed.
"""

import importlib
import importlib.util
import sys
from pathlib import Path

from nexusformat.nexus import NeXusError

LOCAL = 'nx-local'
SMALL = 'nx-small'
LARGE = 'nx-large'


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


def enabled(options, key, default=True):
    """Return a setting as a boolean.

    Settings read from the server's ini file are strings, so the words
    conventionally meaning false have to be recognized as such.

    Parameters
    ----------
    options : dict
        Settings from the `[parsl]` section.
    key : str
        Name of the setting.
    default : bool, optional
        Value to use when the setting is absent, by default True.
    """
    value = option(options, key, default)
    if isinstance(value, str):
        return value.strip().lower() not in ['', '0', 'false', 'no', 'off']
    return bool(value)


def init_commands(options):
    """Return the commands that prepare the environment on each node.

    The `worker_init` setting names a shell script, either absolute or
    relative to the server directory, which is sourced in the batch job
    before the workers are started. Sourcing it rather than running it
    means the module loads, the activated environment and any exported
    variables are inherited by the workers, and by every task they run.

    The path is resolved when the configuration is built, so the submit
    script names the script by its absolute path and does not depend on
    `NX_SERVER` being set within the job. The script does have to be
    readable from the compute nodes: on systems that require jobs to
    declare the filesystems they use, the one holding it must be named
    in the `filesystems` setting.

    Parameters
    ----------
    options : dict
        Settings from the `[parsl]` section.

    Returns
    -------
    list of str
        Commands to run before the workers, empty if `worker_init` is
        unset.
    """
    setting = option(options, 'worker_init')
    if not setting:
        return []
    path = Path(str(setting).strip()).expanduser()
    if not path.is_absolute():
        path = Path(option(options, 'directory', '.')) / path
    if not path.exists():
        raise NeXusError(
            f"Worker initialization script '{path}' does not exist")
    return [f'source {path}']


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
    if not enabled(options, 'monitoring'):
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
        Settings from the `[parsl]` section, with `server_type`, `cores`
        and the server `directory` added by the server.
    run_dir : str or Path
        Directory for Parsl run logs and the monitoring database.

    Notes
    -----
    For `direct` and `multicore` server types, tasks run on the local
    machine using a `LocalProvider`. For `multinode`, the built-in
    default uses PBS Pro (via `nxrefine.parsl.pbs`). Sites using Slurm,
    Grid Engine, or another scheduler should set the `config` option to
    a module that supplies its own `get_config`, for example::

        config = nxrefine.parsl.polaris
    """
    from parsl.config import Config

    run_dir = Path(run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)
    local = option(options, 'server_type') != 'multinode'

    if local:
        executors = [local_executor(options)]
    else:
        from .pbs import pbs_executor
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
    is unset, this package's own defaults are used.

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
