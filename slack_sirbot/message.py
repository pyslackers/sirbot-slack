import logging
import json

from sirbot.message import Message, Content

from .__meta__ import DATA as METADATA
from .user import User
from .channel import Channel
from .errors import SlackMessageError

logger = logging.getLogger('sirbot.slack')


class SlackMessage(Message):
    def __init__(self, *args, timestamp=0, as_user=True, mention=False,
                 **kwargs):
        super().__init__(*args, content=SlackContent, **kwargs)
        self.timestamp = timestamp
        self.as_user = as_user
        self.type = METADATA['name']
        self.mention = mention

    def serialize(self):
        data = self.content.serialize()
        if data.get('text') is False and data.get('attachments') is None:
            logger.warning('Message must have text or an attachments')
            raise SlackMessageError('No text or attachments')
        data['channel'] = self.to.send_id
        data['ts'] = self.timestamp
        data['as_user'] = self.as_user
        return data

    def response(self):
        rep = SlackMessage(to=self.to,
                           frm=self.frm,
                           incoming=self,
                           timestamp=self.timestamp)
        return rep

    @property
    def attachments(self):
        """
        Attachments of the Message
        Shortcut to access 'self.content.attachments'
        """
        return self.content.attachments

    @property
    def username(self) -> str:
        """
        Username used by the bot for this message if not default

        Shortcut to access 'self.content.data['username']'
        """
        return self.content.data['username']

    @username.setter
    def username(self, username: str):
        """
        Change the username of the bot for this message only.

        The as_user variable must be set to False.
        """
        self.content.data['as_user'] = False
        self.content.data['username'] = username

    @property
    def icon(self) -> str:
        """
        Icon used by the bot for this message if not default

        Shortcut to access 'self.content.data['icon_emoji']'
        or 'self.content.data['icon_url']'.
        If both value are set 'icon_emoji' is used first by the
        Slack API.
        """
        return self.content.data['icon_emoji'] or self.content.data['icon_url']

    @icon.setter
    def icon(self, icon: str):
        """
        Change the avatar of the bot for this message only.

        Change the bot avatar to an emoji or url to an image
        (See Slack API documentation for more information
        about the image size)
        The username attribute must be set for this to work.

        :param icon: emoji or url to use
        :type icon: str
        """
        if icon.startswith(':'):
            self.content.data['icon_emoji'] = icon
        else:
            self.content.data['icon_emoji'] = None
            self.content.data['icon_url'] = icon

    @property
    def is_direct_msg(self) -> bool:
        return isinstance(self.to, User)

    @property
    def is_channel_msg(self):
        return isinstance(self.to, Channel)


class SlackContent(Content):

    def __init__(self):
        super().__init__()
        self.attachments = list()

    def serialize(self):
        self.data['attachments'] = list()
        for attachment in self.attachments:
            self.data['attachments'].append(attachment.serialize())
        self.data['attachments'] = json.dumps(self.data['attachments'])
        return self.data


class Attachment:
    """
    Class of a message attachment.

    An attachment can have multiple fields or actions. See
    Slack API documentation for more information about
    attachments.
    """

    def __init__(self, fallback, **kwargs):
        """
        :param fallback: String displayed if the client can not display
        attachments
        """
        self.data = {'mrkdwn_in': ["pretext", "text", "fields"],
                     'fallback': fallback}
        self.fields = list()
        self.actions = list()
        self._add(**kwargs)

    def _add(self, **kwargs):
        for item, value in kwargs.items():
            self.data[item] = value

    def serialize(self):
        self.data['fields'] = list()
        self.data['actions'] = list()
        for field in self.fields:
            self.data['fields'].append(field.serialize())
        for action in self.actions:
            self.data['actions'].append(action.serialize())
        return self.data


class _Action:
    """
    Class representing an action in an Attachment.

    Only one type of action (Button) exist at the moment.
    See Slack API documentation for more information about
    actions.
    """

    def __init__(self, name, text, type_, **kwargs):
        """
        :param name: Name of the action. Sent to the callback url
        :param text: User facing text
        :param type_: Type of action. Only 'button' available
        """
        self.data = {'name': name, 'text': text, 'type': type_}
        self._add(**kwargs)

    def _add(self, **kwargs):
        for item, value in kwargs.items():
            self.data[item] = value

    def serialize(self):
        return self.data

    @property
    def text(self):
        """
        User facing label
        """
        return self.data['text']

    @text.setter
    def text(self, value):
        self.data['text'] = value

    @property
    def style(self):
        """
        Style of the action.

        Currently available: 'default', 'primary', 'danger'
        See Slack API documentation for more information
        """
        return self.data['style']

    @style.setter
    def style(self, value):
        self.data['style'] = value

    @property
    def value(self):
        """
        String identifying the specific action.

        Sent to the callback url alongside 'name' and 'callback_id'
        See Slack API documentation for more information
        """
        return self.data['value']

    @value.setter
    def value(self, value):
        self.data['value'] = value

    @property
    def confirm(self):
        """
        JSON used to display a confirmation message.

        See Slack API documentation for more information
        """
        return self.data['confirm']

    @confirm.setter
    def confirm(self, value):
        self.data['confirm'] = value


class Button(_Action):
    """
    Subclass of action representing a button.

    See Slack API documentation for more information.
    """

    def __init__(self, name, text, **kwargs):
        super().__init__(name=name, text=text, type_='button', **kwargs)


class Field:
    """
    Class representing a field in an attachment.

    See slack API documentation for more information.
    """

    def __init__(self, **kwargs):
        self.data = dict()
        self._add(**kwargs)

    def _add(self, **kwargs):
        for item, value in kwargs.items():
            self.data[item] = value

    @property
    def title(self):
        return self.data['title']

    @title.setter
    def title(self, value):
        self.data['title'] = value

    @property
    def value(self):
        """
        Text/Value to show
        """
        return self.data['value']

    @value.setter
    def value(self, value):
        self.data['value'] = value

    @property
    def short(self):
        """
        Display fields side by side

        Specify if the fields is short enough to be displayed side by side
        in the Attachment.
        """
        return self.data['short']

    @short.setter
    def short(self, value):
        self.data['short'] = value

    @short.deleter
    def short(self):
        self.data.pop('short', None)

    def serialize(self):
        return self.data
