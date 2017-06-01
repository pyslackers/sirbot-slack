import logging

from .store.user import User

logger = logging.getLogger(__name__)


class SlackFacade:
    """
    A class to compose all available functionality of the slack plugin.

    An instance is offered to all incoming message of all the plugins to
    allow cross service messages
    """

    def __init__(self, http_client, users, channels, groups, messages,
                 bot, facades):

        self._facades = facades
        self._http_client = http_client

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

            if self.bot.type == 'rtm' and isinstance(message.to, User):
                await self.users.ensure_dm(message.to)

            message.frm = self.bot

            if message.response_url:
                # Message with a response url are response to actions or slash
                # commands
                data = message.serialize(type_='response')
                await self._http_client.response(data=data,
                                                 url=message.response_url)
            else:
                data = message.serialize(type_='send', to=self.bot.type)
                message.raw = await self._http_client.send(data=data)
                # await self._save_outgoing_message(message)

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
            message.raw = await self._http_client.update(message=message)
            message.ts = message.raw.get('ts')

            # await self._save_outgoing_message(message)

    async def delete(self, *messages):
        """
        Delete the messages provided

        :param messages: Messages to delete
        """
        for message in messages:
            message.timestamp = await self._http_client.delete(message)

    async def add_reaction(self, *messages):
        """
        Add a reaction to a message

        :Example:

        >>> chat.add_reaction([Message, 'thumbsup'], [Message, 'robotface'])
        Add the thumbup and robotface reaction to the message

        :param messages: List of message and reaction to add
        """
        for message, reaction in messages:

            if message.to.id == self.bot.id:
                message.to = message.frm

            if isinstance(message.to, User):
                await self.users.ensure_dm(message.to)

            await self._http_client.add_reaction(message, reaction)

    async def delete_reaction(self, *messages):
        """
        Delete reactions from messages

        :Example:

        >>> chat.delete_reaction([Message, 'thumbsup'], [Message, 'robotface'])
        Delete the thumbup and robotface reaction from the message

        :param messages: List of message and reaction to delete
        """
        for message, reaction in messages:
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
