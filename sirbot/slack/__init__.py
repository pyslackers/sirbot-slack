from sirbot.core import hookimpl as sirbothook
from .core import SirBotSlack
from . import message  # noqa

__version__ = SirBotSlack.__version__


@sirbothook
def plugins(loop):
    return SirBotSlack(loop=loop)
