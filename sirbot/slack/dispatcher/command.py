import asyncio
import inspect
import logging

from aiohttp.web import Response
from sirbot.utils import ensure_future

from .dispatcher import SlackDispatcher
from .. import database
from ..errors import SlackUnknownCommand
from ..store.message.command import SlackCommand

logger = logging.getLogger(__name__)


class CommandDispatcher(SlackDispatcher):
    def __init__(self, http_client, users, channels, groups, plugins, registry,
                 save, loop, token):

        super().__init__(
            http_client=http_client,
            users=users,
            channels=channels,
            groups=groups,
            plugins=plugins,
            registry=registry,
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

        slack = self._registry.get('slack')
        settings = self._endpoints.get(data['command'])

        if not settings:
            raise SlackUnknownCommand(data['command'])

        command = await SlackCommand.from_raw(data, slack, settings=settings)

        if isinstance(self._save, list) and data['command'] in self._save \
                or self._save is True:
            logger.debug('Saving incoming command %s from %s',
                         command.command, command.frm.id)
            db = self._registry.get('database')
            await database.__dict__[db.type].dispatcher.save_incoming_command(
                db, command)
            await db.commit()

        coroutine = settings['func'](command, slack, self._registry)
        ensure_future(coroutine=coroutine, loop=self._loop, logger=logger)

        # if settings.get('public'):
        #     return Response(
        #         status=200,
        #         body=json.dumps({"response_type": "in_channel"}),
        #         content_type='application/json'
        #     )
        # else:
        return Response(status=200)

    def register(self, command, func, public=False):
        logger.debug('Registering slash command: %s, %s from %s',
                     command,
                     func.__name__,
                     inspect.getabsfile(func))

        if not asyncio.iscoroutinefunction(func):
            func = asyncio.coroutine(func)

        settings = {'func': func, 'public': public}
        self._endpoints[command] = settings
