import logging
import asyncio
import time
import json

from aiohttp.web import Response

from ..__meta__ import DATA as METADATA
from ..user import User
from ..channel import Channel
from .event import SlackEventDispatcher
from .message import SlackMessageDispatcher
from .command import SlackCommandDispatcher
from .action import SlackActionDispatcher


logger = logging.getLogger('sirbot.slack')


class SlackMainDispatcher:
    """
    Main dispatcher for the slack plugin.

    Sir-bot-a-lot core dispatch message to the incoming  method.
    """

    def __init__(self, http_client, users, channels, pm, facades, config,
                 verification, *, loop):
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
        self._verification_token = verification

        self._message_dispatcher = None
        self._event_dispatcher = None
        self._command_dispatcher = None

    async def incoming_rtm(self, msg, msg_type):
        """
        Handle the incoming message

        This method is called for every incoming messages
        """
        facades = self._facades.new()
        slack = facades.get(METADATA['name'])
        logger.debug('Incoming event: %s', msg_type)

        # Wait for the plugin to be fully started before dispatching incoming
        # messages

        if msg_type == 'message':
            # Send message to the message dispatcher and exit
            await self._message_dispatcher.incoming(msg,
                                                    slack,
                                                    facades)
        elif msg_type in ('hello', 'reconnect_url', None):
            logging.debug('Ignoring event %s', msg)
        elif msg_type == 'connected':
            await self._login(msg)
        else:
            await self._event_dispatcher.incoming(msg_type,
                                                  msg,
                                                  slack,
                                                  facades)

    async def incoming_command(self, request):
        """
        handle the incoming slash command request

        :param request: aiohttp request
        """

        data = await request.post()

        if data['token'] != self._verification_token:
            return Response(text='Invalid')

        facades = self._facades.new()
        slack = facades.get(METADATA['name'])
        logger.debug('Incoming slash command: %s', data['command'])
        try:
            return await self._command_dispatcher.incoming(
                data,
                slack,
                facades
            )
        except Exception as e:
            logger.exception(e)
            return Response(text='Something went wrong. Please try later')

    async def incoming_button(self, request):
        """
        handle the incoming buttons request

        :param request: aiohttp request
        """

        data = await request.post()

        if 'payload' not in data:
            return Response(text='Invalid', status=400)

        payload = json.loads(data['payload'])

        if 'token' not in payload \
                or payload['token'] != self._verification_token:
            return Response(text='Invalid', status=400)

        facades = self._facades.new()
        slack = facades.get(METADATA['name'])
        try:
            return await self._action_dispatcher.incoming(
                json.loads(data['payload']),
                slack,
                facades
            )
        except Exception as e:
            logger.exception(e)
            return Response(text='Something went wrong. Please try later')

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
        )

        self._event_dispatcher = SlackEventDispatcher(
            pm=self._pm,
            loop=self._loop,
            save=self._config.get('save', {}).get('events', [])
        )

        self._command_dispatcher = SlackCommandDispatcher(
            users=self._users,
            channels=self._channels,
            pm=self._pm,
            loop=self._loop,
            save=self._config.get('save', {}).get('commands', [])
        )

        self._action_dispatcher = SlackActionDispatcher(
            users=self._users,
            channels=self._channels,
            pm=self._pm,
            loop=self._loop,
            save=self._config.get('save', {}).get('commands', [])
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
