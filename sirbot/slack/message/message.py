import json
import logging

from ..errors import SlackMessageError
from ..store.user import User

logger = logging.getLogger('sirbot.slack')


class SlackMessage:
    def __init__(self, to, frm=None, mention=False, text='', subtype='message',
                 conversation=None, content=None, timestamp=None, raw=None,
                 response_url=None, response_type='in_channel',
                 replace_original=True):

        self.to = to
        self.frm = frm
        self.mention = mention
        self.subtype = subtype
        self.timestamp = timestamp
        self.conversation = conversation
        self.raw = raw
        self.response_type = response_type
        self.replace_original = replace_original

        self.content = content or SlackContent()
        self.content.text = text
        self.response_url = response_url

    @property
    def text(self):
        return self.content.text

    @text.setter
    def text(self, text):
        self.content.text = text

    @property
    def attachments(self):
        return self.content.attachments

    @attachments.setter
    def attachments(self, attachments):
        self.content.attachments = attachments

    def serialize(self, type_='send'):

        if type_ == 'response':
            data = self.content.serialize(attachment_type='string')
            data['response_type'] = self.response_type
            data['replace_original'] = self.replace_original
        else:
            data = self.content.serialize(attachment_type='json')

        data['channel'] = self.to.send_id

        if self.timestamp:
            data['ts'] = self.timestamp

        return data

    def response(self):

        if isinstance(self.to, User):
            rep = SlackMessage(
                to=self.frm,
                mention=False,
                conversation=self.conversation,
                response_type=self.response_type
            )
        else:
            rep = SlackMessage(
                to=self.to,
                mention=False,
                conversation=self.conversation,
                response_type=self.response_type
            )

        return rep

    def clone(self):
        """
        Clone the message except the content
        :return: Message
        """
        return SlackMessage(
            to=self.to,
            frm=self.frm,
            mention=self.mention,
            subtype=self.subtype,
            conversation=self.conversation,
            response_type=self.response_type,
            replace_original=self.replace_original
        )

    @classmethod
    async def from_raw(cls, data, slack):

        text = data.get('text') or data.get('message', {}).get('text', '')
        user_id = data.get('user') or data.get('message', {}).get('user')
        channel_id = data.get('channel') or data.get('message', {}).get(
            'channel')
        timestamp = data.get('ts') or data.get('message', {}).get('ts')
        subtype = data.get('subtype') or data.get('message', {}).get('subtype',
                                                                     'message')
        if subtype == 'message_changed':
            timestamp = data.get('message', {}).get('ts', timestamp)

        if user_id:
            frm = await slack.users.get(user_id)
        else:
            bot_id = data.get('bot_id')\
                or data.get('message', {}).get('bot_id')

            if bot_id == slack.bot.bot_id:
                frm = slack.bot
            else:
                frm = None

        if channel_id.startswith('D'):
            mention = True
            to = slack.bot
        elif channel_id.startswith('C'):
            mention = False
            to = await slack.channels.get(channel_id)
        else:
            mention = False
            to = await slack.groups.get(channel_id)

        if slack.bot.id in text:
            mention = True
            bot_link = '<@{}>'.format(slack.bot.id)
            if text.startswith(bot_link):
                text = text[len(bot_link):].strip()

        content = SlackContent(
            text=text
        )

        message = SlackMessage(
            mention=mention,
            to=to,
            frm=frm,
            text=text,
            subtype=subtype,
            conversation=timestamp,
            timestamp=timestamp,
            content=content,
            raw=data,
        )

        return message


class SlackContent:
    def __init__(self, text='', attachments=None, username=None, icon=None,
                 markdown=True):
        if attachments is None:
            attachments = list()

        self.attachments = attachments
        self.text = text
        self.username = username
        self.icon = icon
        self.markdown = markdown

    def serialize(self, attachment_type='json'):
        data = dict()

        if not self.text and not self.attachments:
            raise SlackMessageError('No text or attachments')

        if self.text:
            data['text'] = self.text

        if self.attachments:
            attachments = [attachment.serialize() for attachment in
                           self.attachments]

            if attachment_type == 'json':
                data['attachments'] = json.dumps(attachments)
            else:
                data['attachments'] = attachments

        data['as_user'] = False
        if self.username:
            data['username'] = self.username

        if self.icon:
            if self.icon.startswith(':'):
                data['icon_emoji'] = self.icon
            else:
                data['icon_url'] = self.icon

        data['mrkdwn'] = self.markdown
        return data
