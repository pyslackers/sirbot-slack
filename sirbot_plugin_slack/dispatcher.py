import logging
import asyncio
import re
import inspect

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

    def __init__(self, http_client, users, channels, pm, facades, store,
                 *, loop):
        self._loop = loop or asyncio.get_event_loop()

        self._config = None
        self.bot_id = None
        self._facades = None

        self.started = False

        self._pm = pm
        self._http_client = http_client
        self._users = users
        self._channels = channels
        self._facades = facades
        self._store = store

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
                if self._store is True:
                    db = facades.get('database')
                    await self._store_incoming(msg, db)

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

    async def _store_incoming(self, msg, db):
        await db.execute('''INSERT INTO slack_messages
                          (ts, channel, user, text)
                          VALUES (?, ?, ?, ?)
                          ''',
                         (msg['ts'], msg['channel'], msg['user'], msg['text'])
                         )
        await db.commit()

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

        self._message_dispatcher = SlackMessageDispatcher(self._users,
                                                          self._channels,
                                                          self.bot_id,
                                                          self._pm,
                                                          loop=self._loop)

        self._event_dispatcher = SlackEventDispatcher(self._pm,
                                                      loop=self._loop)
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
    def __init__(self, users, channels, bot_id, pm, *, loop):
        self.commands = defaultdict(list)
        self.mention_commands = defaultdict(list)
        self._users = users
        self._channels = channels
        self.bot_id = bot_id
        self.bot_name = '<@{}>'.format(bot_id)
        self._register(pm)
        self._loop = loop

    async def incoming(self, msg, slack_facade, facades):
        """
        Handler for the incoming events of type 'message'

        Create a message object from the incoming message and sent it
        to the plugins

        :param msg: incoming message
        :return:
        """
        logger.debug('Message handler received %s', msg)
        ignoring = ['message_changed', 'message_deleted', 'channel_join',
                    'channel_leave', 'bot_message', 'message_replied']

        if msg.get('subtype') in ignoring:
            logger.debug('Ignoring %s subtype', msg.get('subtype'))
            return

        message = await self._parse_message(msg, facades.get('database'))
        if message:
            await self._dispatch(message, slack_facade, facades)

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
                msg['match'] = msg['match'].format(bot_name=self.bot_name)
                if msg.get('on_mention'):
                    logger.debug('Registering on mention message: '
                                 '%s, %s in %s',
                                 msg['match'],
                                 msg['func'].__name__,
                                 inspect.getabsfile(msg['func']))
                    c = re.compile(msg['match'], msg.get('flags', 0))
                    self.mention_commands[c].append(msg['func'])
                else:
                    logger.debug('Registering message: %s, %s in %s',
                                 msg['match'],
                                 msg['func'].__name__,
                                 inspect.getabsfile(msg['func']))
                    self.commands[re.compile(msg['match'], msg.get('flags', 0)
                                             )].append(msg['func'])

    async def _dispatch(self, msg, slack_facade, facades):
        """
        Dispatch an incoming slack message to the correct functions

        :param msg: incoming message
        :param slack_facade: facade of the slack plugin
        :param facades: main facade
        :return: None
        """
        handlers = list()
        if msg.mention:
            for match, funcs in self.mention_commands.items():
                n = match.search(msg.text)
                if n:
                    logger.debug('Located handler for "{}", invoking'.format(
                        msg.text))
                    for func in funcs:
                        handlers.append((func, n))

        for match, funcs in self.commands.items():
            n = match.search(msg.text)
            if n:
                logger.debug('Located handler for "{}", invoking'.format(
                    msg.text))
                for func in funcs:
                    handlers.append((func, n))

        for func in handlers:
            f = func[0](msg.response(), slack_facade, facades, func[1])
            ensure_future(coroutine=f, loop=self._loop, logger=logger)


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
