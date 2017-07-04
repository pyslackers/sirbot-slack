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
    SlackAPIError,
    SlackClientError
)

logger = logging.getLogger(__name__)


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
    USER_LIST = SLACK_API_ROOT.format('users.list')

    BOT_INFO = SLACK_API_ROOT.format('bots.info')

    AUTH_TEST = SLACK_API_ROOT.format('auth.test')

    IM_OPEN = SLACK_API_ROOT.format('im.open')
    IM_LIST = SLACK_API_ROOT.format('im.list')


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
            return await self._validate_response(response, url)

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
            return await self._validate_response(response, url)

    async def _validate_response(self, response, url):
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
                logger.debug('Slack HTTP API response: OK for %s', url)
                return rep
            else:
                logger.warning('Slack HTTP API response: %s for %s', rep, url)
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

    async def message_delete(self, message):
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

    async def message_send(self, data, token='app'):
        """
        Send a new message

        :param message: Message to send
        :type message: Message
        :return: Raw message content
        """
        logger.debug('Message Sent: %s', data)
        if token == 'bot':
            rep = await self._do_post(APIPath.MSG_POST,
                                      msg=data,
                                      token=self._bot_token)
        else:
            rep = await self._do_post(APIPath.MSG_POST, msg=data)

        rep['message']['channel'] = rep['channel']
        return rep['message']

    async def response(self, data, url):
        """
        Send a message in response to a slash command / an action

        :param message: Message to send
        :type message: Message
        :return: Slack API response ('ok')
        """
        logger.debug('Message Sent: %s', data)
        rep = await self._do_json(url, msg=data)
        return rep

    async def message_update(self, message):
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
        await self._do_post(APIPath.REACT_ADD, msg=msg, token=self._bot_token)

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

    def _prepare_reaction(self, message, reaction: str = ''):
        """
        Format the message and reaction for the Slack API
        :param message: Message to add/delete/get reaction
        :param reaction: Reaction to add/delete
        :return: Formatted message
        :rtype: dict
        """
        msg = dict()
        msg['channel'] = message.to.send_id
        msg['name'] = reaction
        msg['timestamp'] = message.timestamp
        return msg

    async def get_channels(self, members=False, archived=False):
        """
        Query all available channels in the teams and identify in witch
        channel the bot is present.

        :return: two list of channels. First one contain the channels where the
        bot is present. Second one contain all the available channels of the
        team.
        """
        logger.debug('Getting channels')
        data = {
            'exclude_members': members,
            'exclude_archived': archived
        }
        rep = await self._do_post(APIPath.CHANNEL_GET, msg=data)
        channels = [data for data in rep.get('channels', [])]

        return channels

    async def get_channel(self, channel_id: str):
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

    async def get_group(self, group_id: str):
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

    async def get_users(self):

        rep = await self._do_post(APIPath.USER_LIST)
        return rep['members']

    async def get_user(self, user_id: str):
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

    async def open_dm(self, user_id: str):
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

    async def get_dms(self):

        rep = await self._do_post(APIPath.IM_LIST, token=self._bot_token)
        return rep

    async def get_bot(self, bot=None):

        rep = await self._do_post(APIPath.BOT_INFO, msg={'bot': bot})
        return rep['bot']

    async def rtm_connect(self):
        rep = await self._do_post(APIPath.RTM_CONNECT, token=self._bot_token)
        return rep

    async def auth_test(self):
        rep = await self._do_post(APIPath.AUTH_TEST)
        return rep


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
        self._closed = asyncio.Event(loop=self._loop)
        self._callback = callback

    @property
    def is_closed(self) -> bool:
        """bool: Indicates if the websocket connection is closed."""
        return self._closed.is_set()

    async def _negotiate_rtm_url(self):
        """
        Get the RTM url
        """
        data = await self._do_post(APIPath.RTM_CONNECT)
        if data.get('ok') is False:
            raise SlackConnectionError(
                'Error with slack {}'.format(data))

        return data

    async def reconnect(self):
        logger.warning('Trying to reconnect to slack')
        try:
            self._closed.set()
            await self._ws.close()
            await self.connect()
        except SlackClientError:
            await asyncio.sleep(1, loop=self._loop)
            await self.reconnect()
        except Exception as e:
            logger.exception(e)

    async def connect(self, url=None):
        """
        Connect to the websocket stream and iterate over the messages
        dumping them in the Queue.
        """
        logger.debug('Connecting...')
        try:
            if not url:
                url = (await self._negotiate_rtm_url())['url']
            async with self._session.ws_connect(url) as self._ws:
                self._closed.clear()
                async for data in self._ws:
                    if data.type == aiohttp.WSMsgType.TEXT:
                        if data.data == 'close cmd':
                            await self._ws.close()
                            break
                        else:
                            msg = json.loads(data.data)
                            ensure_future(self._callback(msg),
                                          loop=self._loop,
                                          logger=logger)
                    elif data.type == aiohttp.WSMsgType.CLOSED:
                        logger.warning('WS CLOSED: %s', data)
                    elif data.type == aiohttp.WSMsgType.ERROR:
                        logger.warning('WS ERROR: %s', data)

            await self.reconnect()

        except asyncio.CancelledError:
            pass
        finally:
            self._closed.set()
            self._ws = None
