import logging

from .store.user import User
from .errors import SlackInactiveDispatcher, SlackNoThread

logger = logging.getLogger(__name__)


class SlackWrapper:
    """
    A class to compose all available functionality of the slack plugin.

    An instance is offered to all incoming message of all the plugins to
    allow cross service messages
    """

    def __init__(self, http_client, users, channels, groups, messages, threads,
                 bot, registry, dispatcher):

        self._registry = registry
        self._http_client = http_client
        self._threads = threads
        self._dispatcher = dispatcher

        self.messages = messages
        self.users = users
        self.channels = channels
        self.groups = groups
        self.bot = bot

    async def send(self, *messages):
        """
        Send the messages provided and update their timestamp

        :param messages: Messages to send
        """
        for message in messages:
            message.frm = self.bot

            if self.bot.type == 'rtm' and isinstance(message.to, User):
                await self.users.ensure_dm(message.to)

            if message.response_url:
                # Message with a response url are response to actions or slash
                # commands
                data = message.serialize(type_='response')
                await self._http_client.response(
                    data=data,
                    url=message.response_url
                )
            elif isinstance(message.to, User) and self.bot.type == 'rtm':
                data = message.serialize(type_='send', to=self.bot.type)
                message.raw = await self._http_client.message_send(
                    data=data,
                    token='bot'
                )
            elif isinstance(message.to, User) and self.bot.type == 'event':
                data = message.serialize(type_='send', to=self.bot.type)
                message.raw = await self._http_client.message_send(data=data)
            else:
                data = message.serialize(type_='send', to=self.bot.type)
                message.raw = await self._http_client.message_send(data=data)

    async def update(self, *messages):
        """
        Update the messages provided and update their timestamp

        :param messages: Messages to update
        """
        for message in messages:

            if isinstance(message.to, User):
                await self.users.ensure_dm(message.to)

            message.frm = self.bot
            message.subtype = 'message_changed'
            message.raw = await self._http_client.message_update(
                message=message)
            message.ts = message.raw.get('ts')

            # await self._save_outgoing_message(message)

    async def delete(self, *messages):
        """
        Delete the messages provided

        :param messages: Messages to delete
        """
        for message in messages:
            message.timestamp = await self._http_client.message_delete(message)

    async def add_reaction(self, message, reaction):
        """
        Add a reaction to a message

        :Example:

        >>> chat.add_reaction(Message, 'thumbsup')
        Add the thumbup and robotface reaction to the message

        :param messages: List of message and reaction to add
        """

        await self._http_client.add_reaction(message, reaction)

    async def delete_reaction(self, message, reaction):
        """
        Delete reactions from messages

        :Example:

        >>> chat.delete_reaction(Message, 'thumbsup')
        Delete the thumbup and robotface reaction from the message

        :param messages: List of message and reaction to delete
        """
        await self._http_client.delete_reaction(message, reaction)

    async def get_reactions(self, message):
        """
        Query the reactions of messages

        :param messages: Messages to query reaction from
        :return: dictionary of reactions by message
        :rtype: dict
        """
        reactions = await self._http_client.get_reaction(message)
        for reaction in reactions:
            reaction['users'] = [
                self.users.get(id_=user_id)
                for user_id in reaction.get('users', list())
            ]

        message.reactions = reactions
        return reactions

    def add_action(self, id_, func, public=False):
        if 'action' in self._dispatcher:
            self._dispatcher['action'].register(id_, func, public=public)
        else:
            raise SlackInactiveDispatcher

    def add_event(self, event, func):
        if 'event' in self._dispatcher:
            self._dispatcher['event'].register(event, func)
        else:
            raise SlackInactiveDispatcher

    def add_command(self, command, func, public=False):
        if 'command' in self._dispatcher:
            self._dispatcher['command'].register(command, func, public=public)
        else:
            raise SlackInactiveDispatcher

    def add_message(self, match, func, flags=0, mention=False, admin=False):
        if 'action' in self._dispatcher:
            self._dispatcher['message'].register(match, func, flags, mention,
                                                 admin)
        else:
            raise SlackInactiveDispatcher

    def add_thread(self, message, func, user_id='all'):

        if message.thread or message.timestamp:
            self._threads[message.thread or message.timestamp][user_id] = func
        else:
            raise SlackNoThread()
