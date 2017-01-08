import pluggy

from .api import RTMClient
from .__meta__ import DATA as METADATA
from .dispatcher import SlackMainDispatcher

hookimpl = pluggy.HookimplMarker('sirbot')


@hookimpl
def clients(loop, queue):
    return METADATA['name'], RTMClient(loop=loop, queue=queue)


@hookimpl
def dispatchers(loop, config):
    return METADATA['name'], \
           SlackMainDispatcher(loop=loop,
                               config=config.get(METADATA['name']))