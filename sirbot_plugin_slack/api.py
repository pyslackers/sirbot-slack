import asyncio
import logging
import aiohttp
import json

from typing import Any, AnyStr, Dict, Optional

from sirbot.utils import ensure_future

from .errors import (
    SlackConnectionError,
    SlackServerError,
    SlackRedirectionError,
    SlackAPIError
)
from .channel import Channel

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

    RTM_START = SLACK_API_ROOT.format('rtm.start')

    USER_INFO = SLACK_API_ROOT.format('users.info')

    IM_OPEN = SLACK_API_ROOT.format('im.open')


class APICaller:
    """
    Helper class for anything that can call the slack API.

    :param token: Slack API Token
    :param loop: Asyncio event loop to run in.
    """
    __slots__ = ('_token', '_loop', '_session')

    def __init__(self, token: str, *,
                 loop: Optional[asyncio.BaseEventLoop]=None,
                 session: aiohttp.ClientSession=None):
        self._token = token
        self._loop = loop or asyncio.get_event_loop()
        self._session = session or aiohttp.ClientSession(loop=self._loop)

    def __del__(self):
        if not self._session.closed:
            self._session.close()

    async def _do_post(self, url: str, *,
                       msg: Optional[Dict[AnyStr, Any]]=None,
                       token: Optional[AnyStr]=None):
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
            if 200 <= response.status < 300:
                rep = await response.json()
                if rep['ok'] is True:
                    logger.debug('Slack HTTP API response: OK')
                    # logger.debug('Web API response: %s', rep)
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
        :return: Timestamp of the message
        """
        logger.debug('Message Sent: %s', message)
        message = message.serialize()
        rep = await self._do_post(APIPath.MSG_POST, msg=message)
        return rep.get('ts')

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
        rep = await self._do_post(APIPath.MSG_UPDATE, msg=message)
        return rep.get('ts')

    async def add_reaction(self, message, reaction: str='thumbsup'):
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

    def _prepare_message(self, message, timestamp: str=None):
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

    def _prepare_reaction(self, message, reaction: str=''):
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
        all_channels = []
        bot_channels = []

        rep = await self._do_post(APIPath.CHANNEL_GET, msg={})
        for chan in rep.get('channels'):
            channel = Channel(channel_id=chan['id'], **chan)
            all_channels.append(channel)
            if chan.get('is_member'):
                bot_channels.append(channel)

        return bot_channels, all_channels

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

        rep = await self._do_post(APIPath.IM_OPEN, msg=msg)
        return rep['channel']['id']


class RTMClient(APICaller):
    """
    Client for the slack RTM API (websocket based API).

    :param token: Slack API Token
    :param loop: Event loop to work in, optional.
    """
    def __init__(self, token, callback,
                 *, loop: Optional[asyncio.BaseEventLoop]=None):

        super().__init__(token, loop=loop)
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
        self._login_data = await self._do_post(APIPath.RTM_START)
        if self._login_data.get('ok') is False:
            raise SlackConnectionError(
                'Error with slack {}'.format(self._login_data))

        # TODO: We will want to make sure to add in re-connection
        #       functionality if there is an error.
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
