import asyncio
import inspect
import logging
import re
from collections import defaultdict
from sqlite3 import IntegrityError

from sirbot.utils import ensure_future

from .dispatcher import SlackDispatcher
from .. import database
from ..store.message import SlackMessage

logger = logging.getLogger(__name__)

IGNORING = ['message_changed', 'message_deleted', 'channel_join',
            'channel_leave', 'message_replied', 'bot_message']


class MessageDispatcher(SlackDispatcher):
    def __init__(self, http_client, users, channels, groups, plugins, facades,
                 threads, save, loop):

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

        self.bot = None
        self._threads = threads

    async def incoming(self, msg):
        """
        Handler for the incoming events of type 'message'

        Create a message object from the incoming message and sent it
        to the plugins

        :param msg: incoming message
        :return:
        """
        logger.debug('Message handler received %s', msg)

        facades = self._facades.new()
        slack = facades.get('slack')
        message = await SlackMessage.from_raw(msg, slack)
        db = facades.get('database')

        if not message.frm:  # Message without frm (i.e: slackbot)
            logger.debug('Ignoring message without frm')
            return
        elif message.subtype in IGNORING:
            logger.debug('Ignoring %s subtype', msg.get('subtype'))
            return

        if isinstance(self._save, list) and message.subtype in self._save \
                or self._save is True:
            try:
                await self._save_incoming(message, db)
            except IntegrityError:
                logger.debug('Message "%s" already saved. Aborting.',
                             message.timestamp)
                return

        if message.frm.id in (self.bot.id, self.bot.bot_id):
            logger.debug('Ignoring message from ourselves')
            return

        await self._dispatch(message, slack, facades, db)

    async def _save_incoming(self, message, db):
        """
        Save incoming message in db

        :param message: message
        :param db: db facade
        :return: None
        """
        logger.debug('Saving incoming msg from %s to %s at %s',
                     message.frm.id, message.to.id, message.timestamp)

        await database.__dict__[db.type].dispatcher.save_incoming_message(
            db, message
        )
        await db.commit()

    def _register(self):
        """
        Find and register the functions handling specifics messages

        hookspecs: def register_slack_events()

        :param pm: pluggy plugin store
        """
        self._endpoints = defaultdict(list)
        all_messages = self._plugins.hook.register_slack_messages()
        for messages in all_messages:
            for msg in messages:
                if not asyncio.iscoroutinefunction(msg['func']):
                    logger.debug('Function is not a coroutine, converting.')
                    msg['func'] = asyncio.coroutine(msg['func'])
                logger.debug('Registering message: %s, %s in %s',
                             msg['match'],
                             msg['func'].__name__,
                             inspect.getabsfile(msg['func']))
                self._endpoints[re.compile(msg['match'],
                                           msg.get('flags', 0))].append(msg)

    async def _dispatch(self, msg, slack_facade, facades, db):
        """
        Dispatch an incoming slack message to the correct functions

        :param msg: incoming message
        :param slack_facade: facade of the slack plugin
        :param facades: main facade
        :return: None
        """
        handlers = list()

        if msg.thread in self._threads:
            if self._threads[msg.thread][1] is True\
                    or msg.frm.id == self._threads[msg.thread][1]:
                logger.debug('Located thread handler for "%s"', msg.thread)
                handlers.append((self._threads[msg.thread][0], ''))
                del self._threads[msg.thread]
        else:
            for match, commands in self._endpoints.items():
                n = match.search(msg.text)
                if n:
                    for command in commands:
                        if command.get('mention') and not msg.mention:
                            continue
                        elif command.get('admin') and not msg.frm.admin:
                            continue

                        logger.debug(
                            'Located handler for "{}", invoking'.format(
                                msg.text))
                        handlers.append((command['func'], n))

        for func in handlers:
            f = func[0](msg, slack_facade, facades, func[1])
            ensure_future(coroutine=f, loop=self._loop, logger=logger)
