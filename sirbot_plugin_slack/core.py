import logging
import os
import pluggy
import importlib
import asyncio

from sirbot import Plugin

from . import hookspecs
from .api import RTMClient, HTTPClient
from .dispatcher import SlackMainDispatcher
from .user import SlackUserManager
from .channel import SlackChannelManager
from .facade import SlackFacade
from .errors import SlackConnectionError

logger = logging.getLogger('sirbot.slack')

MANDATORY_PLUGIN = ['sirbot_plugin_slack.user', 'sirbot_plugin_slack.channel']


class SirBotSlack(Plugin):
    def __init__(self, loop):
        super().__init__(loop)
        logger.debug('Initializing slack plugin')
        self._loop = loop
        self._config = None
        self._facades = None
        self._session = None

        self._token = os.environ.get('SIRBOT_SLACK_TOKEN', '')
        if not self._token:
            raise EnvironmentError(
                'SIRBOT_SLACK_TOKEN environment variable is not set')

        self._dispatcher = None
        self._rtm_client = None
        self._http_client = None
        self._users = None
        self._channels = None

    @property
    def started(self):
        if self._dispatcher:
            return self._dispatcher.started
        return False

    async def configure(self, config, router, session, facades):
        logger.debug('Configuring slack plugin')
        self._config = config
        self._session = session
        self._facades = facades

        self._http_client = HTTPClient(token=self._token, loop=self._loop,
                                       session=self._session)
        self._users = SlackUserManager(self._http_client)
        self._channels = SlackChannelManager(self._http_client)
        pm = self._initialize_plugins()
        store = config.get('store', False)
        self._dispatcher = SlackMainDispatcher(http_client=self._http_client,
                                               users=self._users,
                                               channels=self._channels,
                                               pm=pm,
                                               facades=facades,
                                               loop=self._loop,
                                               store=store)
        self._rtm_client = RTMClient(token=self._token, loop=self._loop,
                                     callback=self.incoming,
                                     session=self._session)

    def facade(self):
        """
        Initialize and return a new facade

        This is called by the core when a for each incoming message and when
        another plugin request a slack facade
        """
        return SlackFacade(self._http_client, self._users,
                           self._channels, self._dispatcher.bot_id)

    async def start(self):
        logger.debug('Starting slack plugin')
        await self._create_db_table()
        await self._rtm_client.connect()

    async def _reconnect(self):
        logger.debug('Trying to reconnect to slack')
        try:
            await self._rtm_client.connect()
        except SlackConnectionError:
            await asyncio.sleep(1, loop=self._loop)
            await self._reconnect()

    async def incoming(self, msg):
        msg_type = msg.get('type', None)

        if msg_type in ('team_migration_started', 'goodbye'):
            logger.debug('Bot needs to reconnect')
            await self._reconnect()
        else:
            await self._dispatcher.incoming(msg, msg_type)

    def _initialize_plugins(self):
        """
        Import and register the plugins

        Most likely composed of functions reacting to events and messages
        """
        logger.debug('Initializing plugins of slack plugin')
        pm = pluggy.PluginManager('sirbot.slack')
        pm.add_hookspecs(hookspecs)

        for plugin in MANDATORY_PLUGIN + self._config.get('plugins', []):
            p = importlib.import_module(plugin)
            pm.register(p)

        return pm

    async def _create_db_table(self):
        db = self._facades.get('database')
        await db.execute('''CREATE TABLE IF NOT EXISTS slack_users (
        id TEXT PRIMARY KEY NOT NULL,
        dm_id TEXT,
        admin BOOLEAN DEFAULT False
        )
        ''')

        await db.execute('''CREATE TABLE IF NOT EXISTS slack_channels (
        id TEXT PRIMARY KEY NOT NULL,
        name TEXT UNIQUE,
        is_member BOOLEAN,
        is_archived BOOLEAN
        )
        ''')

        await db.execute('''CREATE TABLE IF NOT EXISTS slack_messages (
        ts TEXT,
        channel TEXT,
        user TEXT,
        text TEXT,
        PRIMARY KEY (ts, channel)
        )
        ''')

        await db.commit()
