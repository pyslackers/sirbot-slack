import asyncio
import inspect
import json
import logging

from aiohttp.web import Response
from sirbot.utils import ensure_future

from .dispatcher import SlackDispatcher
from .. import database
from ..errors import SlackUnknownAction
from ..store.message.action import SlackAction

logger = logging.getLogger(__name__)


class ActionDispatcher(SlackDispatcher):
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

        if 'payload' not in data:
            return Response(text='Invalid', status=400)

        payload = json.loads(data['payload'])

        if 'token' not in payload or payload['token'] != self._token:
            return Response(text='Invalid', status=400)

        logger.debug('Action handler received: %s', payload)

        facades = self._facades.new()
        slack = facades.get('slack')
        settings = self._endpoints.get(payload['callback_id'])

        if not settings:
            raise SlackUnknownAction(payload)

        action = await SlackAction.from_raw(payload, slack, settings=settings)

        if isinstance(self._save, list) and payload['callback_id'] \
                in self._save or self._save is True:
            logger.debug('Saving incoming action %s from %s',
                         action.callback_id,
                         action.frm.id)
            db = facades.get('database')
            await database.__dict__[db.type].dispatcher.save_incoming_action(
                db, action)
            await db.commit()

        coroutine = settings['func'](action, slack, facades)
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

        :return None
        """
        all_actions = self._plugins.hook.register_slack_actions()
        for actions in all_actions:
            for action in actions:
                if not asyncio.iscoroutinefunction(action['func']):
                    logger.debug('Function is not a coroutine, converting.')
                    action['func'] = asyncio.coroutine(action['func'])
                logger.debug('Registering action: %s, %s from %s',
                             action['callback_id'],
                             action['func'].__name__,
                             inspect.getabsfile(action['func']))
                self._endpoints[action['callback_id']] = action
