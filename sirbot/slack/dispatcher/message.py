import logging
import asyncio
import re
import inspect
import json
import functools
import time
import sqlite3

from collections import defaultdict

from ..message import SlackMessage


logger = logging.getLogger(__name__)


class SlackMessageDispatcher:
    def __init__(self, users, channels, bot, pm, save=None, *, loop):

        if not save:
            save = []

        self.commands = defaultdict(list)
        self.callbacks = dict()
        self.bot = bot
        self._users = users
        self._channels = channels
        self._loop = loop
        self._save = save

        self._register(pm)

    async def incoming(self, msg, slack_facade, facades):
        """
        Handler for the incoming events of type 'message'

        Create a message object from the incoming message and sent it
        to the plugins

        :param msg: incoming message
        :return:
        """
        logger.debug('Message handler received %s', msg)

        message = await SlackMessage.from_raw(msg, slack_facade)
        db = facades.get('database')

        if not message.frm:  # Message without frm (i.e: slackbot)
            return
        elif message.frm.id == self.bot.id:  # Skip message from self
            await self._save_update_incoming(message, db)
            return

        if isinstance(self._save, list) and message.subtype in self._save\
                or self._save is True:
            await self._save_incoming(message, db)

        ignoring = ['message_changed', 'message_deleted', 'channel_join',
                    'channel_leave', 'bot_message', 'message_replied']

        if message.subtype in ignoring:
            logger.debug('Ignoring %s subtype', msg.get('subtype'))
            return

        await self._dispatch(message, slack_facade, facades, db)

    async def _save_incoming(self, message, db):
        """
        Save incoming message in db

        :param msg: message
        :param db: db facade
        :return: None
        """
        logger.debug('Saving incoming msg from %s to %s at %s',
                     message.frm.id, message.to.id, message.timestamp)

        await db.execute('''INSERT INTO slack_messages
                          (ts, from_id, to_id, type, conversation, mention,
                          text, raw)
                          VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                          ''',
                         (message.timestamp, message.frm.id, message.to.id,
                          message.subtype, message.conversation,
                          message.mention, message.text,
                          json.dumps(message.raw))
                         )

        await db.commit()

    async def _save_update_incoming(self, message, db):
        """
        Update incoming message in db.

        Used for self message saved on sending

        :param message: incoming message
        :param db: db facade
        :return: None
        """
        logger.debug('Update self incoming msg to %s at %s',
                     message.to.id, message.timestamp)

        try:
            await self._save_incoming(message, db)
        except sqlite3.IntegrityError:
            await db.execute('''UPDATE slack_messages SET raw=?
                                WHERE ts=?''',
                             (json.dumps(message.raw), message.timestamp)
                             )
            await db.commit()

    def _register(self, pm):
        """
        Find and register the functions handling specifics messages

        hookspecs: def register_slack_events()

        :param pm: pluggy plugin manager
        """
        all_messages = pm.hook.register_slack_messages()
        for messages in all_messages:
            for msg in messages:
                if not asyncio.iscoroutinefunction(msg['func']):
                    logger.debug('Function is not a coroutine, converting.')
                    msg['func'] = asyncio.coroutine(msg['func'])
                logger.debug('Registering message: %s, %s in %s',
                             msg['match'],
                             msg['func'].__name__,
                             inspect.getabsfile(msg['func']))
                msg['match'] = msg['match'].format(
                    bot_name='<@{}>'.format(self.bot.id))
                self.commands[re.compile(msg['match'],
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

        if msg.frm.id in self.callbacks \
                and msg.to.id in self.callbacks[msg.frm.id] \
                and time.time() < self.callbacks[msg.frm.id][msg.to.id][
                    'time'] + self.callbacks[msg.frm.id][msg.to.id]['timeout']:
            logger.debug('Located callback for "{}" in "{}", invoking'.format(
                msg.frm.id, msg.to.id))
            msg.conversation_id = self.callbacks[msg.frm.id][msg.to.id]['id']
            await self._update_conversation_id(msg, db)
            handlers.append((self.callbacks[msg.frm.id][msg.to.id]['func'],
                             'callback'))
            del self.callbacks[msg.frm.id][msg.to.id]
        else:
            for match, commands in self.commands.items():
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
            self.ensure_handler(coroutine=f, msg=msg)

    def ensure_handler(self, coroutine, msg):
        callback = functools.partial(self.handler_done_callback,
                                     msg=msg)
        task = asyncio.ensure_future(coroutine, loop=self._loop)
        task.add_done_callback(callback)

    def handler_done_callback(self, f, msg):

        try:
            result = f.result()
        except Exception as e:
            logger.exception(e)
            raise

        if result and 'func' in result:
            to = result.get('to', msg.to)
            frm = result.get('frm', msg.frm)
            callback = result['func']
            timeout = result.get('timeout', 300)
            conversation_id = msg.conversation_id or msg.timestamp

            if frm.id not in self.callbacks:
                self.callbacks[frm.id] = dict()
            self.callbacks[frm.id][to.id] = {
                'func': callback,
                'time': time.time(),
                'timeout': timeout,
                'id': conversation_id
            }

    async def _update_conversation_id(self, msg, db):
        await db.execute('''UPDATE slack_messages SET conversation=?
                             WHERE ts=?'''
                         , (msg.conversation, msg.timestamp)
                         )
        await db.commit()
