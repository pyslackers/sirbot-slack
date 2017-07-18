import asyncio
import inspect
import logging

from aiohttp.web import Response
from sirbot.core import registry
from sirbot.utils import ensure_future

from .dispatcher import SlackDispatcher
from .. import database
from ..errors import SlackUnknownCommand
from ..store.message.command import SlackCommand

logger = logging.getLogger(__name__)


class CommandDispatcher(SlackDispatcher):
    def __init__(self, http_client, users, channels, groups, plugins,
                 save, loop, token):

        super().__init__(
            http_client=http_client,
            users=users,
            channels=channels,
            groups=groups,
            plugins=plugins,
            save=save,
            loop=loop
        )

        self._token = token

    async def _incoming(self, request):
        data = await request.post()
        data = {**data}

        if data['token'] != self._token:
            return Response(text='Invalid')

        logger.debug('Command handler received: %s', data['command'])

        slack = registry.get('slack')
        func = self._endpoints.get(data['command'])

        if not func:
            raise SlackUnknownCommand(data['command'])

        command = await SlackCommand.from_raw(data, slack)

        if isinstance(self._save, list) and data['command'] in self._save \
                or self._save is True:
            logger.debug('Saving incoming command %s from %s',
                         command.command, command.frm.id)
            db = registry.get('database')
            await database.__dict__[db.type].dispatcher.save_incoming_command(
                db, command)
            await db.commit()

        coroutine = func(command, slack)
        ensure_future(coroutine=coroutine, loop=self._loop, logger=logger)
        return Response(status=200)

    def register(self, command, func):
        logger.debug('Registering slash command: %s, %s from %s',
                     command,
                     func.__name__,
                     inspect.getabsfile(func))

        if not asyncio.iscoroutinefunction(func):
            func = asyncio.coroutine(func)

        self._endpoints[command] = func
