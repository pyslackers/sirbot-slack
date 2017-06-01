import asyncio
import inspect
import json
import logging

from aiohttp.web import Response
from sirbot.utils import ensure_future

from .dispatcher import SlackDispatcher
from .. import database
from ..errors import SlackUnknownCommand
from ..store.message.command import SlackCommand

logger = logging.getLogger(__name__)


class CommandDispatcher(SlackDispatcher):
    def __init__(self, http_client, users, channels, groups, plugins, facades,
                 save, loop, token):

        super().__init__(
            http_client=http_client,
            users=users,
            channels=channels,
            groups=groups,
            plugins=plugins,
            facades=facades,
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

        facades = self._facades.new()
        slack = facades.get('slack')
        settings = self._endpoints.get(data['command'])

        if not settings:
            raise SlackUnknownCommand(data['command'])

        command = await SlackCommand.from_raw(data, slack, settings=settings)

        if isinstance(self._save, list) and data['command'] in self._save \
                or self._save is True:
            logger.debug('Saving incoming command %s from %s',
                         command.command, command.frm.id)
            db = facades.get('database')
            await database.__dict__[db.type].dispatcher.save_incoming_command(
                db, command)
            await db.commit()

        coroutine = settings['func'](command, slack, facades)
        ensure_future(coroutine=coroutine, loop=self._loop, logger=logger)

        if settings.get('public'):
            return Response(
                status=200,
                body=json.dumps({"response_type": "in_channel"}),
                content_type='application/json; charset=utf-8'
            )
        else:
            return Response(status=200)

    def _register(self):
        """
        Find and register the functions handling specifics events

        hookspecs: def register_slack_events()

        :param pm: pluggy plugin store
        :return None
        """
        all_commands = self._plugins.hook.register_slack_commands()
        for commands in all_commands:
            for command in commands:
                if not asyncio.iscoroutinefunction(command['func']):
                    logger.debug('Function is not a coroutine, converting.')
                    command['func'] = asyncio.coroutine(command['func'])
                logger.debug('Registering slash command: %s, %s from %s',
                             command['command'],
                             command['func'].__name__,
                             inspect.getabsfile(command['func']))
                self._endpoints[command['command']] = command
