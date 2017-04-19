import json
import logging

from .errors import SlackMessageError
from .user import User

logger = logging.getLogger('sirbot.slack')


class SlackMessage:
    def __init__(self, to, frm=None, mention=False, text='', subtype='message',
                 conversation=None, content=None, timestamp=None, raw=None):

        self.to = to
        self.frm = frm
        self.mention = mention
        self.subtype = subtype
        self.timestamp = timestamp
        self.conversation = conversation
        self.raw = raw

        self.content = content or SlackContent()
        self.content.text = text

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

    def serialize(self):
        data = self.content.serialize()
        data['channel'] = self.to.send_id

        if self.timestamp:
            data['ts'] = self.timestamp

        return data

    def response(self):

        if isinstance(self.to, User):
            rep = SlackMessage(
                to=self.frm,
                mention=False,
                conversation=self.conversation
            )
        else:
            rep = SlackMessage(
                to=self.to,
                mention=False,
                conversation=self.conversation
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
            conversation=self.conversation
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
        else:
            mention = False
            to = await slack.channels.get(channel_id)

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
            raw=data
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

    def serialize(self):
        data = dict()

        if not self.text and not self.attachments:
            raise SlackMessageError('No text or attachments')

        if self.text:
            data['text'] = self.text

        if self.attachments:
            attachments = [attachment.serialize() for attachment in
                           self.attachments]
            data['attachments'] = json.dumps(attachments)

        if self.username:
            data['as_user'] = False
            data['username'] = self.username
        else:
            data['as_user'] = True

        if self.icon:
            if self.icon.startswith(':'):
                data['icon_emoji'] = self.icon
            else:
                data['icon_url'] = self.icon

        data['mrkdwn'] = self.markdown

        return data


class Attachment:
    """
    Class of a message attachment.

    An attachment can have multiple fields or actions. See
    Slack API documentation for more information about
    attachments.
    """

    def __init__(self, fallback, text='', markdown=None, fields=None,
                 actions=None, color=None, pretext='', author_name='',
                 author_link='', author_icon='', title='', title_link='',
                 image_url=None, thumb_url=None, footer='', footer_icon=None,
                 timestamp=None, callback_id=None):
        """
        :param fallback: String displayed if the client can not display
        attachments
        """
        if not markdown:
            markdown = ['pretext', 'text', 'fields']

        if not fields:
            fields = list()

        if not actions:
            actions = list()

        self.text = text
        self.markdown = markdown
        self.fallback = fallback
        self.color = color
        self.pretext = pretext
        self.author_name = author_name
        self.author_link = author_link
        self.author_icon = author_icon
        self.title = title
        self.title_link = title_link
        self.image_url = image_url
        self.thumb_url = thumb_url
        self.footer = footer
        self.footer_icon = footer_icon
        self.timestamp = timestamp
        self.callback_id = callback_id

        self.fields = fields
        self.actions = actions

    def serialize(self):

        data = {
            'fallback': self.fallback,
            'mrkdwn_in': self.markdown,
            'attachment_type': 'default'
        }

        if self.text:
            data['text'] = self.text

        if self.color:
            data['color'] = self.color

        if self.pretext:
            data['pretext'] = self.pretext

        if self.author_name:
            data['author_name'] = self.author_name

            if self.author_icon:
                data['author_icon'] = self.author_icon

            if self.author_link:
                data['author_link'] = self.author_link

        if self.title:
            data['title'] = self.title

            if self.title_link:
                data['title_link'] = self.title_link

        if self.image_url:
            data['image_url'] = self.image_url

        if self.thumb_url:
            data['thumb_url'] = self.thumb_url

        if self.footer:
            data['footer'] = self.footer

            if self.footer_icon:
                data['footer_icon'] = self.footer_icon

        if self.timestamp:
            data['ts'] = self.timestamp

        if self.callback_id:
            data['callback_id'] = self.callback_id

        if self.fields:
            data['fields'] = [field.serialize() for field in self.fields]

        if self.actions:
            data['actions'] = [action.serialize() for action in self.actions]

        return data


class Field:
    """
    Class representing a field in an attachment.

    See slack API documentation for more information.
    """

    def __init__(self, title, value, short=False):
        self.title = title
        self.value = value
        self.short = short

    def serialize(self):
        data = {
            'title': self.title,
            'value': self.value,
            'short': self.short
        }

        return data


class _Action:
    """
    Class representing an action in an Attachment.

    See Slack API documentation for more information about
    actions.
    """

    def __init__(self, type_, name, text=''):
        self.type_ = type_
        self.name = name
        self.text = text

    def serialize(self):
        data = {
            'type': self.type_,
            'name': self.name,
            'text': self.text
        }

        return data


class Button(_Action):
    """
    Subclass of action representing a button.

    See Slack API documentation for more information.
    """

    def __init__(self, name, value, text='', style=None, confirm=None):

        if not confirm:
            confirm = dict()

        super().__init__(type_='button', name=name, text=text)

        self.value = value
        self.confirm = confirm
        self.style = style

    def serialize(self):
        data = super().serialize()

        data['value'] = self.value

        if self.confirm:
            data['confirm'] = self.confirm

        if self.style:
            data['style'] = self.style

        return data


class Select(_Action):
    """
    Subclass of action representing a menu.

    See Slack API documentation for more information.
    """

    def __init__(self, name, text='', options=None, data_source='static',
                 option_groups=None, selected_options=None,
                 min_query_lenght=1):

        if not options:
            options = list()

        if not option_groups:
            option_groups = list()

        if not selected_options:
            selected_options = list()

        super().__init__(type_='select', name=name, text=text)

        self.data_source = data_source
        self.options = options
        self.option_groups = option_groups
        self.selected_options = selected_options
        self.min_query_length = min_query_lenght

    def serialize(self):
        data = super().serialize()

        data['data_source'] = self.data_source

        if self.data_source == 'static':

            if self.option_groups:
                data['option_groups'] = self.option_groups
            else:
                data['options'] = self.options
        elif self.data_source == 'external':
            data['min_query_length'] = self.min_query_length

        if self.selected_options:
            data['selected_options'] = self.selected_options

        return data
