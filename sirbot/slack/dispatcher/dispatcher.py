import logging

from aiohttp.web import Response

logger = logging.getLogger(__name__)


class SlackDispatcher:

    def __init__(self, http_client, users, channels, groups, plugins, registry,
                 loop, save=None):

        if not save:
            save = list()

        self._loop = loop
        self._registry = registry
        self._save = save
        self._plugins = plugins
        self._users = users
        self._channels = channels
        self._groups = groups
        self._http_client = http_client

        self._endpoints = dict()

    async def incoming(self, item):
        try:
            rep = await self._incoming(item)
            return rep
        except Exception as e:
            logger.exception(e)
            return Response(text='Something went wrong. Please try later')

    async def _incoming(self, item):
        pass

    def register(self):
        pass
