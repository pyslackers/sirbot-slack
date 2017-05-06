from sirbot.core.hookimpl import hookimpl as sirbothook
from .core import SirBotSlack

__version__ = SirBotSlack.__version__


@sirbothook
def plugins(loop):
    return SirBotSlack(loop=loop)
