"""
Hookspecs of the slack plugin
"""

import pluggy

hookspec = pluggy.HookspecMarker('sirbot.slack')


@hookspec
def register_slack_events():
    """
    Events hook
    """
    pass


@hookspec
def register_slack_messages():
    """
    Messages hook
    """
    pass


@hookspec
def register_slack_commands():
    """
    Messages hook
    """
    pass


@hookspec
def register_slack_actions():
    """
    Messages hook
    """
    pass
