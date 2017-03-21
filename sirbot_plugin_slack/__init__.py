from .core import SirBotSlack

from sirbot.hookimpl import hookimpl


__version__ = SirBotSlack.__version__


@hookimpl
def plugins(loop):
    return SirBotSlack(loop=loop)
