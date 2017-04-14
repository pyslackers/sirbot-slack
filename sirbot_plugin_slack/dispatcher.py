import logging
import asyncio
import re
import inspect
import json
import functools
import time

from collections import defaultdict

from .__meta__ import DATA as METADATA

from .message import SlackMessage
from .user import User
from .channel import Channel

from sirbot.utils import ensure_future

logger = logging.getLogger('sirbot.slack')


class SlackMainDispatcher:
    """
    Main dispatcher for the slack plugin.

    Sir-bot-a-lot core dispatch message to the incoming  method.
    """

    def __init__(self, http_client, users, channels, pm, facades, config,
                 *, loop):
        self._loop = loop or asyncio.get_event_loop()

        self._config = config
        self.bot_id = None
        self._facades = None

        self.started = False

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
        db = self._facades.get('database')
        await self._parse_channels(login_data['channels'], db=db)
        await self._parse_channels(login_data['groups'], db=db)
        await self._parse_users(login_data['users'], db=db)
        self.bot_id = login_data['self']['id']

        self._message_dispatcher = SlackMessageDispatcher(
            self._users,
            self._channels,
            self.bot_id,
            self._pm,
            self._config.get('save', {}).get('message', False),
            loop=self._loop
        )

        self._event_dispatcher = SlackEventDispatcher(
            self._pm,
            loop=self._loop
        )

        await db.commit()
        self.started = True

    async def _parse_channels(self, channels, db):
        """
        Parse the channels at login and add them to the channel manager if
        the bot is in them
        """
        for channel in channels:
            c = Channel(id_=channel['id'],
                        name=channel['name'],
                        is_member=channel.get('is_member', False),
                        is_archived=channel.get('is_archived', False))
            await self._channels.add(c, db=db)

    async def _parse_users(self, users, db):
        """
        Parse the users at login and add them in the user manager
        """
        for user in users:
            u = User(id_=user['id'],
                     admin=user.get('is_admin', False))
            await self._users.add(u, db=db)


class SlackMessageDispatcher:
    def __init__(self, users, channels, bot_id, pm, save, *, loop):
        self.commands = defaultdict(list)
        self.callbacks = dict()
        self._users = users
        self._channels = channels
        self.bot_id = bot_id
        self.bot_name = '<@{}>'.format(bot_id)
        self._register(pm)
        self._loop = loop
        self._save = save

    async def incoming(self, msg, slack_facade, facades):
        """
        Handler for the incoming events of type 'message'

        Create a message object from the incoming message and sent it
        to the plugins

        :param msg: incoming message
        :return:
        """
        logger.debug('Message handler received %s', msg)

        if self._save is True:
            db = facades.get('database')
            await self._store_incoming(msg, db)

        ignoring = ['message_changed', 'message_deleted', 'channel_join',
                    'channel_leave', 'bot_message', 'message_replied']

        if msg.get('subtype') in ignoring:
            logger.debug('Ignoring %s subtype', msg.get('subtype'))
            return

        message = await self._parse_message(msg, facades.get('database'))
        if message:
            await self._dispatch(message, slack_facade, facades)

    async def _store_incoming(self, msg, db):
        """
        Store incoming message in db

        :param msg: message
        :param db: db facade
        :return: None
        """
        logger.debug('Saving incoming msg in %s at %s', msg['channel'],
                     msg['ts'])
        if 'attachment' in msg:
            attachment = len(msg['attachment'])
        else:
            attachment = 0

        await db.execute('''INSERT INTO slack_messages
                          (ts, channel, user, text, type, attachment, raw,
                           conversation_id)
                          VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                          ''',
                         (msg['ts'], msg['channel'], msg.get('user'),
                          msg.get('text'), msg.get('subtype'),
                          attachment, json.dumps(msg), msg['ts'])
                         )

        if 'text' not in msg and 'subtype' not in msg:
            logger.warning('Message without subtype and text: %s', msg)

        await db.commit()

    async def _parse_message(self, msg, db):
        """
        Parse incoming message into a SlackMessage

        :param msg: incoming message
        :param channel: channel of the incoming message
        :return: SlackMessage or None
        """
        channel = msg.get('channel', None)

        if channel[0] not in 'CGD':
            logger.debug('Unknown channel, Unable to handle this channel: %s',
                         channel)
            return

        if 'message' in msg:
            text = msg['message']['text']
            user_id = msg['message'].get('bot_id') or msg.get('user')
            timestamp = msg['message']['ts']
        else:
            text = msg['text']
            user_id = msg.get('bot_id') or msg.get('user')
            timestamp = msg['ts']

        if user_id.startswith('B') or user_id == self.bot_id:
            # Ignoring bot messages
            return

        if self.bot_name in text or channel.startswith('D'):
            if text.startswith(self.bot_name):
                text = text[len(self.bot_name):].strip()
            mention = True
        else:
            mention = False

        message = SlackMessage(text=text, timestamp=timestamp, mention=mention)
        message.frm = await self._users.get(user_id, dm=True, db=db,
                                            update=False)

        if channel.startswith('D'):
            message.to = message.frm
        else:
            message.to = await self._channels.get(id_=msg['channel'],
                                                  update=False, db=db)

        return message

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
                msg['match'] = msg['match'].format(bot_name=self.bot_name)
                self.commands[re.compile(msg['match'],
                                         msg.get('flags', 0))].append(msg)

    async def _dispatch(self, msg, slack_facade, facades):
        """
        Dispatch an incoming slack message to the correct functions

        :param msg: incoming message
        :param slack_facade: facade of the slack plugin
        :param facades: main facade
        :return: None
        """
        handlers = list()
        db = facades.get('database')

        if msg.frm.id in self.callbacks \
                and msg.to.id in self.callbacks[msg.frm.id] \
                and time.time() < self.callbacks[msg.frm.id][msg.to.id][
                    'time'] + self.callbacks[msg.frm.id][msg.to.id]['timeout']:
            logger.debug('Located callback for "{}" in "{}", invoking'.format(
                msg.frm.id, msg.to.id))

            msg.previous = await self._find_conversation_messages(
                self.callbacks[msg.frm.id][msg.to.id]['id'], db=db)
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
            f = func[0](msg.response(), slack_facade, facades, func[1])
            self.ensure_handler(coroutine=f, msg=msg, db=db)

    def ensure_handler(self, coroutine, msg, db):
        future_callback = functools.partial(self.handler_done_callback,
                                            msg=msg,
                                            db=db,
                                            loop=self._loop)
        future = asyncio.ensure_future(coroutine, loop=self._loop)
        future.add_done_callback(future_callback)

    def handler_done_callback(self, f, msg, db, loop):
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
        await db.execute('''UPDATE slack_messages SET conversation_id=?
                             WHERE ts=?'''
                         , (msg.conversation_id, msg.timestamp)
                         )
        await db.commit()

    async def _find_conversation_messages(self, conversation_id, db):

        await db.execute('''SELECT * FROM slack_messages
                             WHERE conversation_id=? ORDER BY ts DESC''',
                         (conversation_id,))

        messages = await db.fetchall()
        logger.debug('{} messages found in the'
                     ' conversation'.format(len(messages)))
        return messages


class SlackEventDispatcher:
    def __init__(self, pm, *, loop):
        self.events = defaultdict(list)
        self._register(pm)
        self._loop = loop

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
