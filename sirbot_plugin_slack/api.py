import asyncio
import json
import logging
import aiohttp

from typing import Any, AnyStr, Dict, Optional

from sirbot.utils import ensure_future
from .errors import (
    SlackConnectionError,
    SlackServerError,
    SlackRedirectionError,
    SlackAPIError
)

logger = logging.getLogger('sirbot.slack')


class APIPath:
    """Path definitions for slack"""
    SLACK_API_ROOT = 'https://slack.com/api/{0}'

    REACT_ADD = SLACK_API_ROOT.format('reactions.add')
    REACT_DELETE = SLACK_API_ROOT.format('reactions.remove')
    REACT_GET = SLACK_API_ROOT.format('reactions.get')

    MSG_DELETE = SLACK_API_ROOT.format('chat.delete')
    MSG_POST = SLACK_API_ROOT.format('chat.postMessage')
    MSG_UPDATE = SLACK_API_ROOT.format('chat.update')

    CHANNEL_GET = SLACK_API_ROOT.format('channels.list')
    CHANNEL_INFO = SLACK_API_ROOT.format('channels.info')

    GROUP_GET = SLACK_API_ROOT.format('groups.list')
    GROUP_INFO = SLACK_API_ROOT.format('groups.info')

    RTM_START = SLACK_API_ROOT.format('rtm.start')
    RTM_CONNECT = SLACK_API_ROOT.format('rtm.connect')

    USER_INFO = SLACK_API_ROOT.format('users.info')

    IM_OPEN = SLACK_API_ROOT.format('im.open')


class APICaller:
    """
    Helper class for anything that can call the slack API.

    :param token: Slack API Token
    :param loop: Asyncio event loop to run in.
    """
    __slots__ = ('_bot_token', '_app_token', '_token', '_loop', '_session')

    def __init__(self, bot_token, app_token=None,
                 loop: Optional[asyncio.BaseEventLoop] = None,
                 session: aiohttp.ClientSession = None):

        self._bot_token = bot_token
        self._app_token = app_token
        self._token = app_token or bot_token
        self._loop = loop or asyncio.get_event_loop()
        self._session = session or aiohttp.ClientSession(loop=self._loop)

    def __del__(self):
        if not self._session.closed:
            self._session.close()

    async def _do_post(self, url: str, *,
                       msg: Optional[Dict[AnyStr, Any]] = None,
                       token: Optional[AnyStr] = None):
        """
        Perform a POST request, validating the response code.
        This will throw a SlackAPIError, or decendent, on non-200
        status codes

        :param url: url for the request
        :param msg: payload to send
        :param token: optionally override the set token.
        :type msg: dict
        :return: Slack API Response
        :rtype: dict
        """
        msg = msg or {}
        logger.debug('Querying SLACK HTTP API: %s', url)
        msg['token'] = token or self._token
        async with self._session.post(url, data=msg) as response:
            return await self._validate_response(response)

    async def _do_json(self, url, *, msg=None, token=None):
        """
        Perform a POST request with a json payload,
        validating the response code.
        This will throw a SlackAPIError, or decendent, on non-200
        status codes

        :param url: url for the request
        :param msg: payload to send
        :param token: optionally override the set token.
        :type msg: dict
        :return: Slack API Response
        :rtype: dict
        """
        msg = msg or {}
        logger.debug('Querying SLACK HTTP API: %s', url)
        msg['token'] = token or self._token
        async with self._session.post(
                url=url,
                data=json.dumps(msg),
                headers={'content-type': 'application/json; charset=utf-8'}
        ) as response:
            return await self._validate_response(response)

    async def _validate_response(self, response):
        if 200 <= response.status < 300:

            if response.headers['Content-Type'].startswith('application/json'):
                rep = await response.json()
            else:
                rep = await response.text()
                if rep == 'ok':
                    rep = {'ok': True}
                else:
                    rep = {'ok': False, 'response': rep}

            if rep['ok'] is True:
                logger.debug('Slack HTTP API response: OK')
                return rep
            else:
                logger.warning('Slack HTTP API response: %s', rep)
                raise SlackAPIError(rep)
        elif 300 <= response.status < 400:
            e = 'Redirection, status code: {}'.format(response.status)
            logger.error(e)
            raise SlackRedirectionError(e)
        elif 400 <= response.status < 500:
            e = 'Client error, status code: {}'.format(response.status)
            logger.error(e)
            raise SlackConnectionError(e)
        elif 500 <= response.status < 600:
            logger.debug(await response.text())
            e = 'Server error, status code: {}'.format(response.status)
            raise SlackServerError(e)


class HTTPClient(APICaller):
    """
    Client for the slack HTTP API.

    :param token: Slack API access token
    :param loop: Event loop, optional
    """

    async def delete(self, message):
        """
        Delete a previously sent message

        :param message: Message previously sent
        :type message: Message
        :return: Timestamp of the message
        """
        logger.debug('Message Delete: %s', message)
        message = message.serialize()
        rep = await self._do_post(APIPath.MSG_DELETE, msg=message)
        return rep.get('ts')

    async def send(self, message):
        """
        Send a new message

        :param message: Message to send
        :type message: Message
        :return: Raw message content
        """
        logger.debug('Message Sent: %s', message)
        data = message.serialize(type_='send')
        rep = await self._do_post(
            APIPath.MSG_POST,
            msg=data,
            token=self._bot_token
        )

        return rep

    async def response(self, message):
        """
        Send a message in response to a slash command / an action

        :param message: Message to send
        :type message: Message
        :return: Slack API response ('ok')
        """
        logger.debug('Message Sent: %s', message)
        data = message.serialize(type_='response')
        rep = await self._do_json(message.response_url, msg=data)
        return rep

    async def update(self, message):
        """
        Update a previously sent message

        We assume the timestamp of the previous message is stored in the new
        message. This enable the update of a message without creating a new
        message.

        :param message: New message
        :param timestamp: Timestamp of the message to update
        :return: Timestamp of the message
        """
        logger.debug('Message Update: %s', message)
        message = message.serialize()
        rep = await self._do_post(
            APIPath.MSG_UPDATE,
            msg=message,
            token=self._bot_token
        )

        return rep

    async def add_reaction(self, message, reaction: str = 'thumbsup'):
        """
        Add a reaction to a message

        See Slack API documentation and team settings for available reaction

        :param message: Message to add reaction to
        :param reaction: Reaction to add
        """
        msg = self._prepare_reaction(message, reaction)
        logger.debug('Reaction Add: %s', msg)
        await self._do_post(APIPath.REACT_ADD, msg=msg)

    async def delete_reaction(self, message, reaction: str):
        """
        Delete a reaction from a message

        :param message: Message to delete reaction from
        :param reaction: Reaction to delete
        """
        msg = self._prepare_reaction(message, reaction)
        logger.debug('Reaction Delete: %s', msg)
        await self._do_post(APIPath.REACT_DELETE, msg=msg)

    async def get_reaction(self, message):
        """
        Query all the reactions of a message

        :param message: Message to query reaction from
        :return: List of dictionary with the reaction name, count and users
        as keys
        :rtype: list
        """
        msg = self._prepare_reaction(message)
        msg['full'] = True  # Get all the message information
        logger.debug('Reaction Get: {}'.format(msg))
        rep = await self._do_post(APIPath.REACT_GET, msg=msg)
        return rep.get('message').get('reactions')

    def _prepare_message(self, message, timestamp: str = None):
        """
        Format the message for the Slack API
        :param message: Message to send/update/delete
        :param timestamp: Timestamp of the message
        :return: Formatted msg
        :rtype: dict
        """
        msg = message.serialize()
        if timestamp:
            msg['ts'] = timestamp
        return msg

    def _prepare_reaction(self, message, reaction: str = ''):
        """
        Format the message and reaction for the Slack API
        :param message: Message to add/delete/get reaction
        :param reaction: Reaction to add/delete
        :return: Formatted message
        :rtype: dict
        """
        msg = message.serialize()
        msg['name'] = reaction
        msg['timestamp'] = msg['ts']
        return msg

    async def get_channels(self):
        """
        Query all available channels in the teams and identify in witch
        channel the bot is present.

        :return: two list of channels. First one contain the channels where the
        bot is present. Second one contain all the available channels of the
        team.
        """
        logger.debug('Getting channels')

        rep = await self._do_post(APIPath.CHANNEL_GET, msg={})
        channels = [data for data in rep.get('channels', [])]

        return channels

    async def find_channel(self, name):
        logger.debug('Finding channel: %s', name)
        msg = {'exclude_members': True}

        f = [
            self._do_post(APIPath.CHANNEL_GET, msg=msg),
            self._do_post(APIPath.GROUP_GET)
        ]

        tasks, _ = await asyncio.wait(f, return_when=asyncio.ALL_COMPLETED)

        for task in tasks:
            data = task.result()
            for channel in data.get('channels', data.get('groups', [])):
                if name == channel.get('name'):
                    if channel['id'].startswith('C'):
                        channel = await self.get_channel_info(channel['id'])
                    return channel

    async def get_channel_info(self, channel_id: str):
        """
        Query the information about a channel

        :param channel_id: id of the channel to query
        :return: information
        :rtype: dict
        """
        msg = {
            'channel': channel_id
        }

        rep = await self._do_post(APIPath.CHANNEL_INFO, msg=msg)
        return rep['channel']

    async def get_group_info(self, group_id: str):
        """
        Query the information about a channel

        :param group_id: id of the private channel to query
        :return: information
        :rtype: dict
        """
        msg = {
            'channel': group_id
        }

        rep = await self._do_post(APIPath.GROUP_INFO, msg=msg)
        return rep['group']

    async def get_user_info(self, user_id: str):
        """
        Query the information about an user

        :param user_id: id of the user to query
        :return: information
        :rtype: dict
        """
        msg = {
            'user': user_id
        }

        rep = await self._do_post(APIPath.USER_INFO, msg=msg)
        return rep['user']

    async def get_user_dm_channel(self, user_id: str):
        """
        Query the id of the direct message channel for an user

        :param user_id: id of the user to query
        :return: id of the channel
        :rtype: str
        """

        msg = {
            'user': user_id
        }

        rep = await self._do_post(
            APIPath.IM_OPEN,
            msg=msg,
            token=self._bot_token
        )

        return rep['channel']['id']


class RTMClient(APICaller):
    """
    Client for the slack RTM API (websocket based API).

    :param token: Slack API Token
    :param loop: Event loop to work in, optional.
    """

    def __init__(self, bot_token, callback,
                 *, loop: Optional[asyncio.BaseEventLoop] = None,
                 session: aiohttp.ClientSession = None):

        super().__init__(bot_token, loop=loop, session=session)
        self._ws = None
        self._login_data = None
        self._closed = asyncio.Event(loop=self._loop)
        self._callback = callback

    @property
    def slack_id(self):
        if self._login_data is None:
            return None
        return self._login_data['self']['id']

    @property
    def is_closed(self) -> bool:
        """bool: Indicates if the websocket connection is closed."""
        return self._closed.is_set()

    async def _negotiate_rtm_url(self):
        """
        Get the RTM url
        """
        self._login_data = await self._do_post(APIPath.RTM_CONNECT)
        if self._login_data.get('ok') is False:
            raise SlackConnectionError(
                'Error with slack {}'.format(self._login_data))

        return self._login_data

    async def connect(self):
        """
        Connect to the websocket stream and iterate over the messages
        dumping them in the Queue.
        """
        logger.debug('Connecting...')
        try:
            # TODO: We will need to put in some logic for re-connection
            #       on error.
            login_data = await self._negotiate_rtm_url()
            login_data['type'] = 'connected'
            await self._callback(login_data)
            async with self._session.ws_connect(login_data['url']) as ws:
                async for data in ws:
                    if data.type == aiohttp.WSMsgType.TEXT:
                        if data.data == 'close cmd':
                            await ws.close()
                            break
                        else:
                            msg = json.loads(data.data)
                            ensure_future(self._callback(msg),
                                          loop=self._loop,
                                          logger=logger)
                    elif data.type == aiohttp.WSMsgType.CLOSED:
                        break
                    elif data.type == aiohttp.WSMsgType.ERROR:
                        break

        except asyncio.CancelledError:
            pass
        finally:
            self._closed.set()
            self._ws = None
