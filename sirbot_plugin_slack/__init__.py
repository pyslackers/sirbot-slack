from .__meta__ import DATA as METADATA
from .core import SirBotSlack

from sirbot.hookimpl import hookimpl


__version__ = METADATA['version']


@hookimpl
def plugins(loop):
    return METADATA['name'], SirBotSlack(loop=loop)
