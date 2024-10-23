# -----------------------------------------------------------------------------
# Copyright (c) 2022, Argonne National Laboratory.
#
# Distributed under the terms of an Open Source License.
#
# The full license is in the file LICENSE.pdf, distributed with this software.
# -----------------------------------------------------------------------------

from . import edit_settings, manage_server, manage_workflows


def plugin_menu():
    menu = 'Server'
    actions = []
    actions.append(('Manage Workflows', manage_workflows.show_dialog))
    actions.append(('Manage Server', manage_server.show_dialog))
    actions.append(('Edit Settings', edit_settings.show_dialog))
    return menu, actions
