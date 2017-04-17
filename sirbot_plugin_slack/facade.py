import json
import logging

from .message import SlackMessage

logger = logging.getLogger('sirbot.slack')


class SlackFacade:
    """
    A class to compose all available functionality of the slack plugin.

    An instance is offered to all incoming message of all the plugins to
    allow cross service messages
    """

    def __init__(self, http_client, users, channels, bot, facades):
        self._facades = facades
        self._http_client = http_client

        self.users = users
        self.channels = channels
        self.bot = bot

    async def send(self, *messages):
        """
        Send the messages provided and update their timestamp

        :param messages: Messages to send
        """
        for message in messages:
            message.frm = self.bot
            message.raw = await self._http_client.send(message=message)
            message.timestamp = message.raw.get('ts')
            if not message.conversation_id:
                message.conversation_id = message.timestamp
            await self._save_outgoing_message(message)

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

    async def conversation(self, msg, limit=0):
        query = '''SELECT raw FROM slack_messages
                             WHERE conversation_id=? AND ts <= ?
                             ORDER BY ts DESC'''

        db = self._facades.get('database')

        if limit:
            query += ' LIMIT ?'
            await db.execute(query,
                             (msg.conversation_id, msg.timestamp, limit))
        else:
            await db.execute(query, (msg.conversation_id, msg.timestamp))

        raw_msgs = await db.fetchall()
        return [
            await SlackMessage.from_raw(json.loads(raw_msg['raw']), slack=self)
            for raw_msg in raw_msgs]

    async def _save_outgoing_message(self, message):
        """
        Store outgoing message in db

        :param msg: message
        :param db: db facade
        :return: None
        """
        logger.debug('Saving outgoing msg to %s at %s',
                     message.to.id, message.timestamp)
        db = self._facades.get('database')
        await db.execute('''INSERT INTO slack_messages
                          (ts, from_id, to_id, type, conversation_id, text,
                           raw)
                          VALUES (?, ?, ?, ?, ?, ?, ?)
                          ''',
                         (message.timestamp, message.frm.id, message.to.id,
                          message.subtype, message.conversation_id,
                          message.text, json.dumps(message.raw))
                         )

        await db.commit()
