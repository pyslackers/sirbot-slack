class SlackFacade:
    """
    A class to compose all available functionality of the slack plugin.

    An instance is offered to all incoming message of all the plugins to
    allow cross service messages
    """

    def __init__(self, http_client, users, channels, bot_id):
        self._http_client = http_client
        self.bot_id = bot_id
        self.users = users
        self.channels = channels

    async def send(self, *messages):
        """
        Send the messages provided and update their timestamp

        :param messages: Messages to send
        """
        for message in messages:
            message.timestamp = await self._http_client.send(
                message=message)

    async def update(self, *messages):
        """
        Update the messages provided and update their timestamp

        :param messages: Messages to update
        """
        for message in messages:
            message.timestamp = await self._http_client.update(
                message=message)

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

    async def get_reactions(self, *messages):
        """
        Query the reactions of messages

        :param messages: Messages to query reaction from
        :return: dictionary of reactions by message
        :rtype: dict
        """
        reactions = dict()
        for message in messages:
            msg_reactions = await self._http_client.get_reaction(message)
            for msg_reaction in msg_reactions:
                users = list()
                for user_id in msg_reaction.get('users'):
                    users.append(self.users.get(id_=user_id))
                msg_reaction['users'] = users
            reactions[message] = msg_reactions
            message.reactions = msg_reactions
        return reactions
