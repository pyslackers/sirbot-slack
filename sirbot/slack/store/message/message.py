import json
import logging
import asyncio

from ..user import User
from ...errors import SlackMessageError

logger = logging.getLogger('sirbot.slack')


class SlackMessage:
    def __init__(self, to, frm=None, mention=False, text='', subtype='message',
                 content=None, raw=None, response_url=None,
                 response_type='in_channel', replace_original=True):

        if not raw:
            raw = dict()

        self._to = to

        self.frm = frm
        self.mention = mention
        self.subtype = subtype
        self.raw = raw
        self.response_type = response_type
        self.replace_original = replace_original

        self.content = content or SlackContent()
        self.content.text = text
        self.response_url = response_url
        self._thread_callback = (None, None)

    @property
    def to(self):
        return self._to

    @to.setter
    def to(self, to):
        if self.response_url:
            self.response_url = None
        self._to = to

    @property
    def text(self):
        return self.content.text

    @text.setter
    def text(self, text):
        self.content.text = text

    @property
    def timestamp(self):
        return self.raw.get('ts') or self.raw.get('message', {}).get('ts')

    @timestamp.setter
    def timestamp(self, _):
        raise ValueError

    @property
    def attachments(self):
        return self.content.attachments

    @attachments.setter
    def attachments(self, attachments):
        self.content.attachments = attachments

    @property
    def thread(self):
        return self.raw.get('thread_ts', self.timestamp)

    @thread.setter
    def thread(self, thread_ts):
        self.raw['thread_ts'] = thread_ts

    @property
    def thread_callback(self):
        return self._thread_callback

    @thread_callback.setter
    def thread_callback(self, func):

        if isinstance(func, tuple):
            func, user_id = func
        else:
            user_id = True

        if not asyncio.iscoroutine(func):
            func = asyncio.coroutine(func)
        self._thread_callback = (func, user_id)

    def serialize(self, type_='send', to='rtm'):

        if type_ == 'response':
            data = self.content.serialize(attachment_type='string')
            data['response_type'] = self.response_type
            data['replace_original'] = self.replace_original
        else:
            data = self.content.serialize(attachment_type='json')

        if to == 'event' and isinstance(self.to, User):
            data['channel'] = '@' + self.to.name
        else:
            data['channel'] = self.to.send_id

        if self.timestamp:
            data['ts'] = self.timestamp

        if self.thread != self.timestamp:
            data['thread_ts'] = self.thread

        return data

    def response(self, thread=False):

        if thread:
            raw = {'thread_ts': self.thread}
        else:
            raw = dict()

        if self.to.id.startswith('U'):
            rep = SlackMessage(
                to=self.frm,
                mention=False,
                response_type=self.response_type,
                raw=raw
            )
        else:
            rep = SlackMessage(
                to=self.to,
                mention=False,
                response_type=self.response_type,
                raw=raw
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
            response_type=self.response_type,
            replace_original=self.replace_original
        )

    @classmethod
    async def from_raw(cls, data, slack):

        text = data.get('text') or data.get('message', {}).get('text', '')
        user_id = data.get('user') or data.get('message', {}).get('user')
        channel_id = data.get('channel') or data.get('message', {}).get(
            'channel')
        subtype = data.get('subtype') or data.get('message', {}).get('subtype',
                                                                     'message')

        if user_id:
            frm = await slack.users.get(user_id)
        else:
            bot_id = data.get('bot_id')\
                or data.get('message', {}).get('bot_id')
            frm = await slack.users.get(bot_id)

        if channel_id.startswith('D'):
            mention = True
            to = slack.bot
        elif channel_id.startswith('C'):
            mention = False
            to = await slack.channels.get(channel_id)
        else:
            mention = False
            to = await slack.groups.get(channel_id)

        if slack.bot and slack.bot.id in text:
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
