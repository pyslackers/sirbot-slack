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
from ..store.channel import Channel

logger = logging.getLogger(__name__)


class MessageDispatcher(SlackDispatcher):
    def __init__(self, http_client, users, channels, groups, plugins, registry,
                 threads, save, loop, ping):

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

        self.bot = None
        self._threads = threads
        self._endpoints = defaultdict(list)

        if ping:
            self._ping_emoji = ping
            self.register(match='', func=self._ping, mention=True)

    async def incoming(self, msg):
        """
        Handler for the incoming events of type 'message'

        Create a message object from the incoming message and sent it
        to the plugins

        :param msg: incoming message
        :return:
        """
        logger.debug('Message handler received %s', msg)

        slack = self._registry.get('slack')
        message = await SlackMessage.from_raw(msg, slack)
        db = self._registry.get('database')

        if not message.frm:  # Message without frm (i.e: slackbot)
            logger.debug('Ignoring message without frm')
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

        await self._dispatch(message, slack, self._registry, db)

    async def _save_incoming(self, message, db):
        """
        Save incoming message in db

        :param message: message
        :param db: db plugin
        :return: None
        """
        logger.debug('Saving incoming msg from %s to %s at %s',
                     message.frm.id, message.to.id, message.timestamp)

        await database.__dict__[db.type].dispatcher.save_incoming_message(
            db, message
        )
        await db.commit()

    def register(self, match, func, flags=0, mention=False, admin=False):

        logger.debug('Registering message: %s, %s from %s',
                     match,
                     func.__name__,
                     inspect.getabsfile(func))

        if not asyncio.iscoroutinefunction(func):
            func = asyncio.coroutine(func)

        option = {
            'func': func,
            'mention': mention,
            'admin': admin
        }

        self._endpoints[re.compile(match, flags)].append(option)

    async def _dispatch(self, msg, slack, registry, db):
        """
        Dispatch an incoming slack message to the correct functions

        :param msg: incoming message
        :param slack: slack plugin
        :param registry: plugin registry
        :return: None
        """
        handlers = list()

        if msg.thread in self._threads:
            if msg.frm.id in self._threads[msg.thread]:
                logger.debug('Located thread handler for "%s" and "%s"',
                             msg.thread, msg.frm.id)
                handlers.append((self._threads[msg.thread][msg.frm.id], None))
                del self._threads[msg.thread][msg.frm.id]
            elif 'all' in self._threads[msg.thread]:
                logger.debug('Located thread handler for "%s"', msg.thread)
                handlers.append((self._threads[msg.thread]['all'], None))
                del self._threads[msg.thread]['all']

        if not handlers:
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
            f = func[0](msg, slack, registry, func[1])
            ensure_future(coroutine=f, loop=self._loop, logger=logger)

    async def _ping(self, message, slack, *_):

        if isinstance(message.to, Channel):
            await slack.add_reaction(message, self._ping_emoji)
