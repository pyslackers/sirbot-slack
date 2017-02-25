from .__meta__ import DATA as METADATA
from .api import RTMClient
from .dispatcher import SlackMainDispatcher

from sirbot.hookimpl import hookimpl


@hookimpl
def clients(loop, queue):
    return METADATA['name'], RTMClient(loop=loop, queue=queue)


@hookimpl
def dispatchers(loop):
    return METADATA['name'], \
           SlackMainDispatcher(loop=loop)
