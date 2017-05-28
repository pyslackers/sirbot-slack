import logging
import asyncio
import inspect
import time
import json

from aiohttp.web import Response

from .dispatcher import SlackDispatcher
from .message import MessageDispatcher
from .. import database
from collections import defaultdict
from sirbot.utils import ensure_future


logger = logging.getLogger(__name__)


class EventDispatcher(SlackDispatcher):
    def __init__(self, http_client, users, channels, groups, plugins, facades,
                 event_save, msg_save, loop, bot, token):

        super().__init__(
            http_client=http_client,
            users=users,
            channels=channels,
            groups=groups,
            plugins=plugins,
            facades=facades,
            save=event_save,
            loop=loop
        )

        self._message_dispatcher = MessageDispatcher(
            http_client=http_client,
            users=users,
            channels=channels,
            groups=groups,
            plugins=plugins,
            facades=facades,
            save=msg_save,
            loop=loop,
            bot=bot
        )

        self._token = token

    async def incoming(self, item):
        pass

    async def incoming_rtm(self, event):

        try:
            if event['type'] == 'message':
                await self._message_dispatcher.incoming(event)
            else:
                await self._incoming(event)
        except Exception as e:
            logger.exception(e)

    async def incoming_web(self, request):
        payload = await request.json()

        if payload['token'] != self._token:
            return Response(text='Invalid')

        if payload['type'] == 'url_verification':
            body = json.dumps({'challenge': payload['challenge']})
            return Response(body=body, status=200)

        try:
            if payload['event']['type'] == 'message':
                ensure_future(
                    self._message_dispatcher.incoming(payload['event']),
                    loop=self._loop,
                    logger=logger
                )
            else:
                ensure_future(
                    self._incoming(payload['event']),
                    loop=self._loop,
                    logger=logger
                )
            return Response(status=200)
        except Exception as e:
            logger.exception(e)
            return Response(status=500)

    async def _incoming(self, event):

        facades = self._facades.new()
        slack = facades.get('slack')

        if isinstance(self._save, list) and event['type'] in self._save \
                or self._save is True:
            db = facades.get('database')
            await self._store_incoming(event, db)

        for func in self._endpoints.get(event['type'], list()):
            f = func(event, slack, facades)
            ensure_future(coroutine=f, loop=self._loop, logger=logger)

    def _register(self):
        """
        Find and register the functions handling specifics events

        hookspecs: def register_slack_events()

        :param pm: pluggy plugin store
        :return None
        """
        self._endpoints = defaultdict(list)
        all_events = self._plugins.hook.register_slack_events()
        for events in all_events:
            for event in events:
                if not asyncio.iscoroutinefunction(event['func']):
                    logger.debug('Function is not a coroutine, converting.')
                    event['func'] = asyncio.coroutine(event['func'])
                logger.debug('Registering event: %s, %s from %s',
                             event['event'],
                             event['func'].__name__,
                             inspect.getabsfile(event['func']))
                self._endpoints[event['event']].append(event['func'])

    async def _store_incoming(self, event, db):
        """
        Store incoming event in db

        :param msg: message
        :param db: db facade
        :return: None
        """
        ts = event.get('ts') or time.time()
        user = event.get('user')

        if isinstance(user, dict):
            user = user.get('id')

        logger.debug('Saving incoming event %s from %s', event['type'], user)
        await database.__dict__[db.type].dispatcher.save_incoming_event(
            ts=ts, user=user, event=event, db=db
        )

        await db.commit()
