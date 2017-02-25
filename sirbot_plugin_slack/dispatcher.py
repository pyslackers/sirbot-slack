import logging
import asyncio
import re
import inspect
import pluggy
import importlib

from collections import defaultdict

from . import hookspecs
from .__meta__ import DATA as METADATA

from sirbot.hookimpl import hookimpl

from .message import SlackMessage
from .facade import SlackFacade
from .user import SlackUserManager, User
from .channel import SlackChannelManager, Channel
from .api import HTTPClient

logger = logging.getLogger('sirbot.slack')


class SlackMessageDispatcher:
    def __init__(self, users, channels, bot_id, pm):
        super().__init__()
        self.commands = defaultdict(list)
        self.mention_commands = defaultdict(list)
        self._users = users
        self._channels = channels
        self.bot_name = '<@{}>'.format(bot_id)

        self._register(pm)

    async def incoming(self, msg, chat, facades):
        """
        Handler for the incoming message of type 'message'

        Create a message object from the incoming message and sent it
        to the plugins

        :param msg: incoming message
        :return:
        """
        logger.debug('Message handler received %s', msg)
        ignoring = ['message_changed', 'message_deleted', 'channel_join',
                    'channel_leave', 'bot_message']
        channel = msg.get('channel', None)

        if msg.get('subtype') in ignoring:
            logger.debug('Ignoring %s subtype', msg.get('subtype'))
            return

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

        mention = False
        if text.startswith(self.bot_name):
            text = text[len(self.bot_name):].strip()
            mention = True
        if channel[0] == 'D':
            mention = True

        if user_id.startswith('B'):
            # Bot message
            return

        message = SlackMessage(text=text, timestamp=timestamp, mention=mention)
        if channel.startswith('D'):
            # If the channel starts with D it is a direct message to the bot
            user = await self._users.get(user_id)
            user.send_id = channel
            message.frm = user
            message.to = user
        else:
            message.frm = await self._users.get(user_id, dm=True)
            message.to = await self._channels.get(id_=msg['channel'])

        await self._dispatch(message, chat, facades)

    def _register(self, pm):
        """
        Find and register the functions handling specifics messages
        """
        all_messages = pm.hook.register_slack_messages()
        for messages in all_messages:
            for msg in messages:
                if not asyncio.iscoroutinefunction(msg['func']):
                    logger.debug('Function is not a coroutine, converting.')
                    msg['func'] = asyncio.coroutine(msg['func'])
                msg['match'] = msg['match'].format(bot_name=self.bot_name)
                if msg.get('on_mention'):
                    logger.debug('Registering new on mention message: '
                                 '%s, %s in %s',
                                 msg['match'],
                                 msg['func'].__name__,
                                 inspect.getabsfile(msg['func']))
                    self.mention_commands[re.compile(msg['match'],
                                                     msg.get('flags', 0)
                                                     )].append(msg['func'])
                else:
                    logger.debug('Registering new message: %s, %s in %s',
                                 msg['match'],
                                 msg['func'].__name__,
                                 inspect.getabsfile(msg['func']))
                    self.commands[re.compile(msg['match'], msg.get('flags', 0)
                                             )].append(msg['func'])

    async def _dispatch(self, msg, chat, facades):
        """
        Dispatch an incoming slack message to the correct functions
        """
        if msg.mention:
            for match, funcs in self.mention_commands.items():
                n = match.search(msg.text)
                if n:
                    logger.debug('Located handler for "{}", invoking'.format(
                        msg.text))
                    for func in funcs:
                        await func(msg.response(), chat, n.groups(), facades)

        for match, funcs in self.commands.items():
            n = match.search(msg.text)
            if n:
                logger.debug('Located handler for "{}", invoking'.format(
                    msg.text))
                for func in funcs:
                    await func(msg.response(), chat, n.groups(), facades)


class SlackMainDispatcher:
    def __init__(self, loop):

        self._loop = loop or asyncio.get_event_loop()
        self._config = None

        logger.debug('Starting SlackMainDispatcher')

        self.events = defaultdict(list)
        self._started = False
        self._pm = None
        self._id = None
        self._http_client = HTTPClient(loop=loop)
        self._users = SlackUserManager(self._http_client)
        self._channels = SlackChannelManager(self._http_client)
        self._message_dispatcher = None

    def configure(self, config):
        """
        Set the config
        """
        self._config = config
        if 'loglevel' in config:
            logger.setLevel(config['loglevel'])

        self._pm = self._initialize_plugins()
        self._register(self._pm)

    async def incoming(self, msg, chat, facades):
        """
        Handle the incoming message
        """
        msg_type = msg.get('type', None)
        ok = msg.get('ok', None)
        logger.debug('Incoming event: %s', msg_type)

        if self._started:
            if msg_type == 'message':
                await self._message_dispatcher.incoming(msg, chat, facades)
                return
            elif msg_type == 'hello':
                return
            elif msg_type == "reconnect_url":
                return
            elif ok:
                if msg.get('warning'):
                    logger.warning('API response: %s, %S',
                                   msg.get('warning'), msg)
                else:
                    logger.debug('API response: %s', msg)
            elif ok is False:
                logger.info('API error: %s, %s', msg.get('error'), msg)
            elif msg_type is None:
                logging.debug('Ignoring non event message %s', msg)
                return

            await self._dispatch_event(msg_type, msg, chat, facades)

        elif msg_type == 'connected':
            await self._login(msg)

    async def _login(self, login_data):
        """
        Parse data from the login message to the slack API
        """
        await self._parse_channels(login_data['channels'])
        await self._parse_channels(login_data['groups'], groups=True)
        await self._parse_users(login_data['users'])
        self._id = login_data['self']['id']

        self._message_dispatcher = SlackMessageDispatcher(self._users,
                                                          self._channels,
                                                          self._id,
                                                          self._pm)

        self._started = True
        logger.info('SlackMainDispatcher started !')

    def _initialize_plugins(self):
        """
        Import and register the plugins

        Most likely composed of functions reacting to events and messages
        """
        logger.debug('Initializing slack plugins')
        self._pm = pluggy.PluginManager('sirbot.slack')
        self._pm.add_hookspecs(hookspecs)

        for plugin in self._config['plugins']:
            p = importlib.import_module(plugin)
            self._pm.register(p)

        return self._pm

    def _register(self, pm):
        """
        Find and register the functions handling specifics events
        """
        all_events = pm.hook.register_slack_events()
        for events in all_events:
            for event in events:
                if not asyncio.iscoroutinefunction(event['func']):
                    logger.debug('Function is not a coroutine, converting.')
                    event['func'] = asyncio.coroutine(event['func'])
                logger.debug('Registering new event: %s, %s in %s',
                             event['name'],
                             event['func'].__name__,
                             inspect.getabsfile(event['func']))
                self.events[event['name']].append(event['func'])

    async def _dispatch_event(self, msg_type, msg, chat, facades):
        """
        Dispatch an incoming slack event to the correct functions
        """
        funcs = self.events.get(msg_type)
        if funcs:
            for func in funcs:
                await func(msg, chat, facades)

    async def _parse_channels(self, channels, groups=False):
        """
        Parse the channels at login and add them to the channel manager if
        the bot is in them
        """
        for channel in channels:
            if channel.get('is_member') is True or groups:
                c = Channel(channel_id=channel['id'],
                            type_=METADATA['name'],
                            **channel)
                await self._channels.add(c)

    async def _parse_users(self, users):
        """
        Parse the users at login and add them in the user manager
        """
        for user in users:
            u = User(user['id'], **user)
            await self._users.add(u)

    def facade(self):
        """
        Initialize and return a new facade
        """
        return SlackFacade(self._http_client, self._users,
                           self._channels, self._id)


@hookimpl
def dispatchers(loop):
    return METADATA['name'], SlackMainDispatcher(loop=loop)
