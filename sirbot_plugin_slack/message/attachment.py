import logging

logger = logging.getLogger('sirbot.slack')


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

    def __init__(self, name, value, text='', style='default', confirm=None):

        if not confirm:
            confirm = dict()

        super().__init__(type_='button', name=name, text=text)

        self._style = None

        self.value = value
        self.confirm = confirm
        self.style = style

    @property
    def style(self):
        return self._style

    @style.setter
    def style(self, style):
        if style in ['danger', 'primary', 'default']:
            self._style = style
        else:
            raise ValueError('Style must be one of default, primary, danger')

    def serialize(self):
        data = super().serialize()

        data['value'] = self.value

        if self.confirm:
            data['confirm'] = self.confirm

        if self._style:
            data['style'] = self._style

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

        self._data_source = None
        self.data_source = data_source
        self.options = options
        self.option_groups = option_groups
        self.selected_options = selected_options
        self.min_query_length = min_query_lenght

    @property
    def data_source(self):
        return self._data_source

    @data_source.setter
    def data_source(self, data_source):

        if data_source in ['static', 'external']:
            self._data_source = data_source
        else:
            raise ValueError('data_source must be one of static, external')

    def serialize(self):
        data = super().serialize()

        data['data_source'] = self._data_source

        if self._data_source == 'static':

            if self.option_groups:
                data['option_groups'] = self.option_groups
            else:
                data['options'] = self.options
        elif self._data_source == 'external':
            data['min_query_length'] = self.min_query_length

        if self.selected_options:
            data['selected_options'] = self.selected_options

        return data
