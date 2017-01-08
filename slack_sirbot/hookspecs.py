"""
Hookspecs of the slack plugins
"""

import pluggy

hookspec = pluggy.HookspecMarker('sirbot.slack')


@hookspec
def register_slack_events():
    pass


@hookspec
def register_slack_messages():
    pass
