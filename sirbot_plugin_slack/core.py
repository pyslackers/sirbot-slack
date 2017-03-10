import logging
import os
import pluggy
import importlib

from sirbot import Plugin

from . import hookspecs
from .api import RTMClient, HTTPClient
from .dispatcher import SlackMainDispatcher
from .user import SlackUserManager
from .channel import SlackChannelManager
from .facade import SlackFacade

logger = logging.getLogger('sirbot.slack')

MANDATORY_PLUGIN = ['sirbot_plugin_slack.user', 'sirbot_plugin_slack.channel']


class SirBotSlack(Plugin):
    def __init__(self, loop):
        super().__init__(loop)
        logger.debug('Initializing slack plugin')
        self._loop = loop
        self._config = None
        self._facades = None

        self._token = os.environ.get('SIRBOT_SLACK_TOKEN', '')
        if not self._token:
            raise EnvironmentError(
                'SIRBOT_SLACK_TOKEN environment variable is not set')

        self._dispatcher = None
        self._rtm_client = None

        self._http_client = HTTPClient(token=self._token, loop=loop)
        self._users = SlackUserManager(self._http_client)
        self._channels = SlackChannelManager(self._http_client)

    @property
    def started(self):
        if self._dispatcher:
            return self._dispatcher.started
        return False

    def configure(self, config, router, facades):
        logger.debug('Configuring slack plugin')
        self._config = config

        pm = self._initialize_plugins()
        self._dispatcher = SlackMainDispatcher(http_client=self._http_client,
                                               users=self._users,
                                               channels=self._channels,
                                               pm=pm,
                                               facades=facades,
                                               loop=self._loop)
        self._rtm_client = RTMClient(token=self._token, loop=self._loop,
                                     callback=self._dispatcher.incoming)

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
        await self._rtm_client.connect()

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
