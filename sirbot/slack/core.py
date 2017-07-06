import logging
import os
import yaml

from collections import defaultdict

from sirbot.utils import merge_dict
from sirbot.core import Plugin

from . import database, sync
from .dispatcher import (EventDispatcher,
                         ActionDispatcher,
                         CommandDispatcher,
                         MessageDispatcher)
from .__meta__ import DATA as METADATA
from .api import RTMClient, HTTPClient
from .errors import SlackSetupError
from .store import ChannelStore, UserStore, GroupStore, MessageStore
from .store.user import User
from .wrapper import SlackWrapper

logger = logging.getLogger(__name__)

MANDATORY_PLUGIN = ['sirbot.slack.store.user',
                    'sirbot.slack.store.channel',
                    'sirbot.slack.store.group']

SUPPORTED_DATABASE = ['sqlite']


class SirBotSlack(Plugin):
    __name__ = 'slack'
    __version__ = METADATA['version']

    def __init__(self, loop):
        super().__init__(loop)
        logger.debug('Initializing slack plugin')
        self._loop = loop
        self._router = None
        self._config = None
        self._registry = None
        self._session = None
        self._bot_token = None
        self._app_token = None
        self._verification_token = None
        self._rtm_client = None
        self._http_client = None
        self._users = None
        self._channels = None
        self._groups = None
        self._messages = None
        self._pm = None

        self._threads = defaultdict(dict)
        self._dispatcher = dict()
        self._started = False

        self.bot = None

    @property
    def started(self):
        return self._started

    async def configure(self, config, router, session, registry):
        logger.debug('Configuring slack plugin')
        path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), 'config.yml'
        )

        with open(path) as file:
            defaultconfig = yaml.load(file)

        self._config = merge_dict(config, defaultconfig[self.__name__])

        self._router = router
        self._session = session
        self._registry = registry

        self._bot_token = os.environ.get('SIRBOT_SLACK_BOT_TOKEN', '')
        self._app_token = os.environ.get('SIRBOT_SLACK_TOKEN', '')
        self._verification_token = os.environ.get(
            'SIRBOT_SLACK_VERIFICATION_TOKEN'
        )

        if 'database' not in self._registry:
            raise SlackSetupError('A database is required')

        if not self._bot_token and not self._app_token:
            raise SlackSetupError(
                'One of SIRBOT_SLACK_BOT_TOKEN or SIRBOT_SLACK_TOKEN'
                ' must be set'
            )

        if self._config['rtm'] and not self._bot_token:
            raise SlackSetupError('SIRBOT_SLACK_BOT_TOKEN must be set to use'
                                  'the rtm API')

        if self._app_token and not self._verification_token:
            raise SlackSetupError(
                'SIRBOT_SLACK_VERIFICATION_TOKEN must be set'
            )

        self._http_client = HTTPClient(
            bot_token=self._bot_token,
            app_token=self._app_token,
            loop=self._loop,
            session=self._session
        )

        self._users = UserStore(
            client=self._http_client,
            registry=self._registry,
            refresh=self._config['refresh']['user']
        )

        self._channels = ChannelStore(
            client=self._http_client,
            registry=self._registry,
            refresh=self._config['refresh']['channel']
        )

        self._groups = GroupStore(
            client=self._http_client,
            registry=self._registry,
            refresh=self._config['refresh']['group']
        )

        self._messages = MessageStore(
            client=self._http_client,
            registry=self._registry
        )

        if self._config['rtm'] or self._config['endpoints']['events']:
            logger.debug('Adding events endpoint: %s',
                         self._config['endpoints']['events'])

            self._dispatcher['message'] = MessageDispatcher(
                http_client=self._http_client,
                users=self._users,
                channels=self._channels,
                groups=self._groups,
                plugins=self._pm,
                registry=self._registry,
                save=self._config['save']['messages'],
                ping=self._config['ping'],
                loop=self._loop,
                threads=self._threads
            )

            self._dispatcher['event'] = EventDispatcher(
                http_client=self._http_client,
                users=self._users,
                channels=self._channels,
                groups=self._groups,
                plugins=self._pm,
                registry=self._registry,
                loop=self._loop,
                message_dispatcher=self._dispatcher['message'],
                event_save=self._config['save']['events'],
                token=self._verification_token
            )

            if self._config['rtm']:
                self._rtm_client = RTMClient(
                    bot_token=self._bot_token,
                    loop=self._loop,
                    callback=self._incoming_rtm,
                    session=self._session
                )

            if self._config['endpoints']['events']:
                self._router.add_route(
                    'POST',
                    self._config['endpoints']['events'],
                    self._dispatcher['event'].incoming_web
                )

        if self._config['endpoints']['actions']:
            logger.debug('Adding actions endpoint: %s',
                         self._config['endpoints']['actions'])
            self._dispatcher['action'] = ActionDispatcher(
                http_client=self._http_client,
                users=self._users,
                channels=self._channels,
                groups=self._groups,
                plugins=self._pm,
                registry=self._registry,
                loop=self._loop,
                save=self._config['save']['actions'],
                token=self._verification_token
            )

            self._router.add_route(
                'POST',
                self._config['endpoints']['actions'],
                self._dispatcher['action'].incoming
            )

        if self._config['endpoints']['commands']:
            logger.debug('Adding commands endpoint: %s',
                         self._config['endpoints']['commands'])
            self._dispatcher['command'] = CommandDispatcher(
                http_client=self._http_client,
                users=self._users,
                channels=self._channels,
                groups=self._groups,
                plugins=self._pm,
                registry=self._registry,
                loop=self._loop,
                save=self._config['save']['commands'],
                token=self._verification_token
            )
            self._router.add_route(
                'POST',
                self._config['endpoints']['commands'],
                self._dispatcher['command'].incoming
            )

    def factory(self):
        """
        Initialize and return the slack wrapper

        This is called by the core when a for each incoming message and when
        another plugin request the slack wrapper
        """
        return SlackWrapper(
            http_client=self._http_client,
            users=self._users,
            channels=self._channels,
            groups=self._groups,
            messages=self._messages,
            bot=self.bot,
            registry=self._registry,
            threads=self._threads,
            dispatcher=self._dispatcher
        )

    async def start(self):
        logger.debug('Starting slack plugin')

        db = self._registry.get('database')
        if db.type not in SUPPORTED_DATABASE:
            raise SlackSetupError('Database must be one of %s',
                                  ', '.join(SUPPORTED_DATABASE))

        await self._create_db_table()

        slack = self.factory()
        sync.add_to_slack(slack)

        if self._rtm_client:
            data = await self._http_client.rtm_connect()
            self.bot = await self._users.get(data['self']['id'])
            self.bot.type = 'rtm'
            self._dispatcher['message'].bot = self.bot
            self._dispatcher['event'].bot = self.bot
            await self._rtm_client.connect(url=data['url'])
        else:
            self.bot = User(id_='B000000000')
            self.bot.type = 'event'
            if 'message' in self._dispatcher:
                self._dispatcher['message'].bot = self.bot
            if 'event' in self._dispatcher:
                self._dispatcher['event'].bot = self.bot
            self._started = True

    async def _incoming_rtm(self, event):
        try:
            msg_type = event.get('type', None)

            if msg_type == 'hello':
                self._started = True
            elif self.started:
                if msg_type in ('team_migration_started', 'goodbye'):
                    logger.debug('Bot needs to reconnect')
                    await self._rtm_client.reconnect()
                else:
                    await self._dispatcher['event'].incoming_rtm(event)
        except Exception as e:
            logger.exception(e)

    async def database_update(self, metadata, db):

        if metadata['version'] == '0.0.5':
            await database.__dict__[db.type].update.update_006(db)
            metadata['version'] = '0.0.6'

        if metadata['version'] == '0.0.6':
            await database.__dict__[db.type].update.update_007(db)
            metadata['version'] = '0.0.7'

        if metadata['version'] == '0.0.7':
            await database.__dict__[db.type].update.update_008(db)
            metadata['version'] = '0.0.8'

        return self.__version__

    async def _create_db_table(self):
        db = self._registry.get('database')
        await database.__dict__[db.type].create_table(db)
        await db.set_plugin_metadata(self)
        await db.commit()
