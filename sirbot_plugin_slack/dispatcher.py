import logging
import asyncio
import re
import inspect
import json
import functools
import time
import sqlite3

from collections import defaultdict
from sirbot.utils import ensure_future

from .__meta__ import DATA as METADATA

from .message import SlackMessage
from .user import User
from .channel import Channel


logger = logging.getLogger('sirbot.slack')


class SlackMainDispatcher:
    """
    Main dispatcher for the slack plugin.

    Sir-bot-a-lot core dispatch message to the incoming  method.
    """

    def __init__(self, http_client, users, channels, pm, facades, config,
                 *, loop):
        self._loop = loop or asyncio.get_event_loop()

        self.bot_id = None
        self.bot = None
        self.started = False

        self._facades = None
        self._config = config
        self._pm = pm
        self._http_client = http_client
        self._users = users
        self._channels = channels
        self._facades = facades

        self._message_dispatcher = None
        self._event_dispatcher = None

    async def incoming(self, msg, msg_type):
        """
        Handle the incoming message

        This method is called for every incoming messages
        """
        facades = self._facades.new()
        slack_facade = facades.get(METADATA['name'])
        logger.debug('Incoming event: %s', msg_type)

        # Wait for the plugin to be fully started before dispatching incoming
        # messages
        if self.started:

            if msg_type == 'message':
                # Send message to the message dispatcher and exit
                await self._message_dispatcher.incoming(msg,
                                                        slack_facade,
                                                        facades)
            elif msg_type in ('hello', 'reconnect_url', None):
                logging.debug('Ignoring event %s', msg)
            else:
                await self._event_dispatcher.incoming(msg_type,
                                                      msg,
                                                      slack_facade,
                                                      facades)
        elif msg_type == 'connected':
            await self._login(msg)

    async def _login(self, login_data):
        """
        Parse data from the login event to slack
        and initialize the message and event dispatcher
        """
        logger.debug('Loading teams info')
        await self._parse_channels(login_data['channels'])
        await self._parse_channels(login_data['groups'])
        await self._parse_users(login_data['users'])

        self.bot_id = login_data['self']['id']
        self.bot = await self._users.get(self.bot_id)

        self._message_dispatcher = SlackMessageDispatcher(
            users=self._users,
            channels=self._channels,
            bot=self.bot,
            pm=self._pm,
            save=self._config.get('save', {}).get('message', False),
            loop=self._loop,
            facades=self._facades
        )

        self._event_dispatcher = SlackEventDispatcher(
            pm=self._pm,
            loop=self._loop,
            save=self._config.get('save', {}).get('events', [])
        )

        self.started = True

    async def _parse_channels(self, channels):
        """
        Parse the channels at login and add them to the channel manager if
        the bot is in them
        """

        now = time.time()
        for channel in channels:
            c = Channel(
                id_=channel['id'],
                raw=channel,
                last_update=now,
            )
            await self._channels.add(c)

    async def _parse_users(self, users):
        """
        Parse the users at login and add them in the user manager
        """
        for user in users:
            u = User(id_=user['id'], raw=user, last_update=time.time())
            await self._users.add(u)


class SlackMessageDispatcher:
    def __init__(self, users, channels, bot, pm, facades, save=None, *, loop):

        if not save:
            save = []

        self.commands = defaultdict(list)
        self.callbacks = dict()
        self.bot = bot

        self._users = users
        self._channels = channels
        self._register(pm)
        self._loop = loop
        self._save = save
        self._facades = facades

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
        db = self._facades.get('database')

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
        future_callback = functools.partial(self.handler_done_callback,
                                            msg=msg)
        future = asyncio.ensure_future(coroutine, loop=self._loop)
        future.add_done_callback(future_callback)

    def handler_done_callback(self, f, msg):
        try:
            error = f.exception()
            result = f.result()
        except asyncio.CancelledError:
            return

        if error is not None:
            logger.exception("Task exited with error",
                             exc_info=error)

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


class SlackEventDispatcher:
    def __init__(self, pm, save=None, *, loop):

        if not save:
            save = list()

        self.events = defaultdict(list)
        self._register(pm)
        self._loop = loop
        self._save = save

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
                             event['name'],
                             event['func'].__name__,
                             inspect.getabsfile(event['func']))
                self.events[event['name']].append(event['func'])

    async def _store_incoming(self, event_type, event, db):
        """
        Store incoming event in db

        :param msg: message
        :param db: db facade
        :return: None
        """
        ts = event.get('ts') or time.time()
        user = event.get('user')

        logger.debug('Saving incoming event %s from %s', event_type, user)

        await db.execute('''INSERT INTO slack_events (ts, from_id, type, raw)
                            VALUES (?, ?, ?, ?)''',
                         (ts, user, event_type, json.dumps(event))
                         )
        await db.commit()
