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
from sirbot.plugins.dispatcher import Dispatcher

from .message import SlackMessage
from .facade import SlackFacade
from .user import SlackUserManager, User
from .channel import SlackChannelManager, Channel
from .api import HTTPClient

logger = logging.getLogger('sirbot.slack')


class SlackMainDispatcher(Dispatcher):
    """
    Main dispatcher for the slack plugin.

    Sir-bot-a-lot core dispatch message to the incoming  method.
    """

    def __init__(self, loop):
        logger.debug('Starting SlackMainDispatcher')
        super().__init__(loop=loop)

        self._loop = loop or asyncio.get_event_loop()
        self._config = None
        self._started = False
        self._pm = None
        self._id = None

        self._http_client = HTTPClient(loop=loop)
        self._users = SlackUserManager(self._http_client)
        self._channels = SlackChannelManager(self._http_client)

        self._message_dispatcher = None
        self._event_dispatcher = None

        self.events = defaultdict(list)

    def configure(self, config):
        """
        Configure the slack plugin

        This method is called by the core after initialization
        :param config: configuration relevant to the slack plugin
        """
        self._config = config
        if 'loglevel' in config:
            logger.setLevel(config['loglevel'])

        # Import the subplugins and register them
        self._pm = self._initialize_plugins()

    async def incoming(self, msg, slack_facade, facades):
        """
        Handle the incoming message

        This method is called for every incoming messages
        """
        msg_type = msg.get('type', None)
        logger.debug('Incoming event: %s', msg_type)

        # Wait for the plugin to be fully started before dispatching incoming
        # messages
        if self._started:
            if msg_type == 'message':
                # Send message to the message dispatcher and exit
                await self._message_dispatcher.incoming(msg,
                                                        slack_facade,
                                                        facades)
            elif msg_type in ('hello', 'reconnect_url', None):
                logging.debug('Ignoring event %s', msg)
            else:
                await self._event_dispatcher.incoming(msg_type, msg,
                                                      slack_facade,
                                                      facades)
        elif msg_type == 'connected':
            await self._login(msg)

    async def _login(self, login_data):
        """
        Parse data from the login event to slack
        and initialize the message and event dispatcher
        """
        await self._parse_channels(login_data['channels'])
        await self._parse_channels(login_data['groups'])
        await self._parse_users(login_data['users'])
        self._id = login_data['self']['id']

        self._message_dispatcher = SlackMessageDispatcher(self._users,
                                                          self._channels,
                                                          self._id,
                                                          self._pm)

        self._event_dispatcher = SlackEventDispatcher(self._pm)

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

        for plugin in self._config.get('plugins'):
            p = importlib.import_module(plugin)
            self._pm.register(p)

        return self._pm

    async def _parse_channels(self, channels):
        """
        Parse the channels at login and add them to the channel manager if
        the bot is in them
        """
        for channel in channels:
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

        This is called by the core when a for each incoming message and when
        another plugin request a slack facade
        """
        return SlackFacade(self._http_client, self._users,
                           self._channels, self._id)


class SlackMessageDispatcher:
    def __init__(self, users, channels, bot_id, pm):
        self.commands = defaultdict(list)
        self.mention_commands = defaultdict(list)
        self._users = users
        self._channels = channels
        self.bot_name = '<@{}>'.format(bot_id)
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

        message = await self._parse_message(msg, channel)
        if message:
            await self._dispatch(message, slack_facade, facades)

    async def _parse_message(self, msg, channel):
        """
        Parse incoming message into a SlackMessage

        :param msg: incoming message
        :param channel: channel of the incoming message
        :return: SlackMessage or None
        """
        if 'message' in msg:
            text = msg['message']['text']
            user_id = msg['message'].get('bot_id') or msg.get('user')
            timestamp = msg['message']['ts']
        else:
            text = msg['text']
            user_id = msg.get('bot_id') or msg.get('user')
            timestamp = msg['ts']

        if user_id.startswith('B'):
            # Ignoring bot messages
            return

        if self.bot_name in text or channel.startswith('D'):
            if text.startswith(self.bot_name):
                text = text[len(self.bot_name):].strip()
            mention = True
        else:
            mention = False

        message = SlackMessage(text=text, timestamp=timestamp, mention=mention)

        if channel.startswith('D'):
            # If the channel starts with D it is a direct message to the bot
            user = await self._users.get(id_=user_id, update=False)
            user.send_id = channel
            message.frm = user
            message.to = user
        else:
            message.frm = await self._users.get(user_id, dm=True,
                                                update=False)
            message.to = await self._channels.get(id_=msg['channel'],
                                                  update=False)

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
                    self.mention_commands[re.compile(msg['match'],
                                                     msg.get('flags', 0)
                                                     )].append(msg['func'])
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
            asyncio.ensure_future(func[0](msg.response(),
                                          slack_facade,
                                          facades,
                                          func[1]))


class SlackEventDispatcher:
    def __init__(self, pm):
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
        for func in self.events.get(event_type, list()):
            asyncio.ensure_future(func(event, slack_facade, facades))

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


@hookimpl
def dispatchers(loop):
    return METADATA['name'], SlackMainDispatcher(loop=loop)
