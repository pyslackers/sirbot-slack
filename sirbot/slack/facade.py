import json
import logging
import sqlite3

from .message.message import SlackMessage
from .manager.user import User

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

            if isinstance(message.to, User):
                await self.users.ensure_dm(message.to)

            if message.content.username:
                # Necessary to store the correct event in db
                # Without custom username the message is sent as a regular
                # user
                message.subtype = 'bot_message'

            message.frm = self.bot

            if message.response_url:
                # Message with a response url are response to actions or slash
                # commands
                await self._http_client.response(message=message)
            else:
                message.raw = await self._http_client.send(message=message)
                await self._save_outgoing_message(message)

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

            await self._save_outgoing_message(message)

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
        messages = list()
        for message in raw_msgs:
            m = await SlackMessage.from_raw(
                json.loads(message['raw']),
                slack=self
            )
            messages.append(m)
        return messages

    async def _save_outgoing_message(self, message):
        """
        Store outgoing message in db

        :param msg: message
        :param db: db facade
        :return: None
        """
        message.timestamp = message.raw.get('ts')

        logger.debug('Saving outgoing msg to %s at %s',
                     message.to.id, message.timestamp)

        if not message.conversation:
            message.conversation = message.timestamp

        db = self._facades.get('database')
        try:
            await db.execute('''INSERT INTO slack_messages
                              (ts, from_id, to_id, type, conversation, mention,
                              text, raw)
                              VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                              ''',
                             (message.timestamp, message.frm.id, message.to.id,
                              message.subtype, message.conversation, False,
                              message.text, json.dumps(message.raw))
                             )
        except sqlite3.IntegrityError:
            await db.execute('''UPDATE slack_messages SET conversation=?
                                WHERE ts=?''',
                             (message.conversation, message.timestamp))

        await db.commit()
