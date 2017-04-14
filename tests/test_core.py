import sirbot
import pytest
import asyncio

from sirbot_plugin_slack.errors import SlackAPIError

CONFIG = {
    'core': {
        'plugins': ['sirbot_plugin_slack', ]
    }
}

async def test_no_token(loop, test_server):
    pass
