import asyncio
import inspect
import json
import logging
import time
from collections import defaultdict

from aiohttp.web import Response
from sirbot.utils import ensure_future

from .dispatcher import SlackDispatcher
from .. import database

logger = logging.getLogger(__name__)


IGNORING = ['channel_join', 'channel_leave', 'bot_message']
SUBTYPE_TO_EVENT = ['message_changed', 'message_deleted']


class EventDispatcher(SlackDispatcher):
    def __init__(self, http_client, users, channels, groups, plugins, registry,
                 event_save, message_dispatcher, loop, token):

        super().__init__(
            http_client=http_client,
            users=users,
            channels=channels,
            groups=groups,
            plugins=plugins,
            registry=registry,
            save=event_save,
            loop=loop
        )

        self._endpoints = defaultdict(list)
        self._message_dispatcher = message_dispatcher
        self._token = token
        self.bot = None

    async def incoming(self, item):
        pass

    async def incoming_rtm(self, event):

        try:
            if event['type'] == 'message':
                await self._incoming_message(event)
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
                    self._incoming_message(payload['event']),
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

    async def _incoming_message(self, event):
        subtype = event.get('subtype') or event.get('message', {}).get(
            'subtype', 'message')
        if subtype in IGNORING:
            return
        elif subtype in SUBTYPE_TO_EVENT:
            event['type'] = subtype
            await self._incoming(event)
        else:
            await self._message_dispatcher.incoming(event)

    async def _incoming(self, event):
        logger.debug('Event handler received: %s', event)

        slack = self._registry.get('slack')

        if isinstance(self._save, list) and event['type'] in self._save \
                or self._save is True:
            db = self._registry.get('database')
            await self._store_incoming(event, db)

        for func in self._endpoints.get(event['type'], list()):
            f = func(event, slack, self._registry)
            ensure_future(coroutine=f, loop=self._loop, logger=logger)

    def register(self, event, func):

        logger.debug('Registering event: %s, %s from %s',
                     event,
                     func.__name__,
                     inspect.getabsfile(func))

        if not asyncio.iscoroutinefunction(func):
            func = asyncio.coroutine(func)
        self._endpoints[event].append(func)

    async def _store_incoming(self, event, db):
        """
        Store incoming event in db

        :param msg: message
        :param db: db plugin
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
