import logging
import asyncio
import inspect
import json
import time

from collections import defaultdict
from sirbot.core.utils import ensure_future


logger = logging.getLogger('sirbot.slack')


class SlackEventDispatcher:
    def __init__(self, pm, save=None, *, loop):

        if not save:
            save = list()

        self._loop = loop
        self._save = save

        self.events = defaultdict(list)

        self._register(pm)

    async def incoming(self, event_type, event, slack_facade, facades):
        """
        Handler for the incoming events which are not of type `message`

        Pass the event to the correct functions

        :param event: incoming event
        :param event_type: type of the incoming event
        :param slack_facade: facade of the slack plugin
        :param facades: main facade
        :return: None
        """

        if isinstance(self._save, list) and event_type in self._save \
                or self._save is True:
            db = facades.get('database')
            await self._store_incoming(event_type, event, db)

        for func in self.events.get(event_type, list()):
            f = func(event, slack_facade, facades)
            ensure_future(coroutine=f, loop=self._loop, logger=logger)

    def _register(self, pm):
        """
        Find and register the functions handling specifics events

        hookspecs: def register_slack_events()

        :param pm: pluggy plugin manager
        :return None
        """
        all_events = pm.hook.register_slack_events()
        for events in all_events:
            for event in events:
                if not asyncio.iscoroutinefunction(event['func']):
                    logger.debug('Function is not a coroutine, converting.')
                    event['func'] = asyncio.coroutine(event['func'])
                logger.debug('Registering event: %s, %s from %s',
                             event['event'],
                             event['func'].__name__,
                             inspect.getabsfile(event['func']))
                self.events[event['event']].append(event['func'])

    async def _store_incoming(self, event_type, event, db):
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

        logger.debug('Saving incoming event %s from %s', event_type, user)

        await db.execute('''INSERT INTO slack_events (ts, from_id, type, raw)
                            VALUES (?, ?, ?, ?)''',
                         (ts, user, event_type, json.dumps(event))
                         )
        await db.commit()
