import asyncio
import inspect
import json
import logging

from aiohttp.web import Response
from sirbot.utils import ensure_future

from ..message.action import SlackAction

logger = logging.getLogger('sirbot.slack')


class SlackActionDispatcher:
    def __init__(self, users, channels, pm, save, loop):

        if not save:
            save = list()

        self._users = users
        self._channels = channels
        self._pm = pm
        self._save = save
        self._loop = loop

        self.actions = dict()

        self._register(pm)

    async def incoming(self, data, slack, facades):
        logger.debug('Action handler received %s', data)

        action_settings = self.actions.get(data['callback_id'])
        data = {**data}

        if not action_settings:
            logger.warning('Incoming action (%s) with no handler',
                           data['callback_id'])
            return

        action = await SlackAction.from_raw(
            data,
            slack,
            settings=action_settings
        )

        if isinstance(self._save, list) and data['callback_id'] in self._save \
                or self._save is True:
            db = facades.get('database')
            await self._save_incoming(action, db)

        couroutine = action_settings['func'](action, slack, facades)
        ensure_future(coroutine=couroutine, loop=self._loop, logger=logger)

        if action_settings.get('public'):
            data = {"response_type": "in_channel"}
            return Response(
                status=200,
                body=json.dumps(data),
                content_type='application/json; charset=utf-8'
            )
        else:
            return Response(status=200)

    async def _save_incoming(self, action, db):
        logger.debug('Saving incoming action %s from %s', action.callback_id,
                     action.user.id)

        await db.execute('''INSERT INTO slack_actions
                            (ts, channel, user, callback_id, action, raw)
                            VALUES (?, ?, ?, ?, ?, ?)''',
                         (action.ts, action.channel.id, action.user.id,
                          action.callback_id, json.dumps(action.action),
                          json.dumps(action.raw))
                         )

    def _register(self, pm):
        """
        Find and register the functions handling specifics events

        hookspecs: def register_slack_events()

        :param pm: pluggy plugin manager
        :return None
        """
        all_actions = pm.hook.register_slack_actions()
        for actions in all_actions:
            for action in actions:
                if not asyncio.iscoroutinefunction(action['func']):
                    logger.debug('Function is not a coroutine, converting.')
                    action['func'] = asyncio.coroutine(action['func'])
                logger.debug('Registering action: %s, %s from %s',
                             action['callback_id'],
                             action['func'].__name__,
                             inspect.getabsfile(action['func']))
                self.actions[action['callback_id']] = action
