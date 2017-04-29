import asyncio
import inspect
import json
import logging

from aiohttp.web import Response
from sirbot.utils import ensure_future

from ..message.command import SlackCommand

logger = logging.getLogger('sirbot.slack')


class SlackCommandDispatcher:
    def __init__(self, users, channels, pm, save, loop):

        if not save:
            save = list()

        self._users = users
        self._channels = channels
        self._pm = pm
        self._save = save
        self._loop = loop

        self.commands = dict()

        self._register(pm)

    async def incoming(self, data, slack, facades):
        logger.debug('Command handler received %s', data)

        command_settings = self.commands.get(data['command'])
        data = {**data}

        if not command_settings:
            logger.warning('Incoming slash command (%s) with no handler',
                           data['command'])
            return

        command = await SlackCommand.from_raw(
            data,
            slack,
            settings=command_settings
        )

        if isinstance(self._save, list) and data['command'] in self._save \
                or self._save is True:
            db = facades.get('database')
            await self._save_incoming(command, db)

        couroutine = command_settings['func'](command, slack, facades)
        ensure_future(coroutine=couroutine, loop=self._loop, logger=logger)

        if command_settings.get('public'):
            data = {"response_type": "in_channel"}
            return Response(
                status=200,
                body=json.dumps(data),
                content_type='application/json; charset=utf-8'
            )
        else:
            return Response(status=200)

    async def _save_incoming(self, command, db):
        logger.debug('Saving incoming command %s from %s',
                     command.command, command.frm.id)

        await db.execute('''INSERT INTO slack_commands
                            (ts, to_id, from_id, command, text, raw) VALUES
                            (? ,?, ?, ?, ?, ?)''',
                         (command.timestamp, command.to.id,
                          command.frm.id, command.command, command.text,
                          json.dumps(command.raw))
                         )

        await db.commit()

    def _register(self, pm):
        """
        Find and register the functions handling specifics events

        hookspecs: def register_slack_events()

        :param pm: pluggy plugin manager
        :return None
        """
        all_commands = pm.hook.register_slack_commands()
        for commands in all_commands:
            for command in commands:
                if not asyncio.iscoroutinefunction(command['func']):
                    logger.debug('Function is not a coroutine, converting.')
                    command['func'] = asyncio.coroutine(command['func'])
                logger.debug('Registering slash command: %s, %s from %s',
                             command['command'],
                             command['func'].__name__,
                             inspect.getabsfile(command['func']))
                self.commands[command['command']] = command
