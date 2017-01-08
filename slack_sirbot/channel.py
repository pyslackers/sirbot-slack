import logging

from sirbot.receiver import Receiver

from .hookimpl import hookimpl

logger = logging.getLogger('sirbot.slack')


class Channel(Receiver):
    """
    Class representing a channel.
    """
    def __init__(self, channel_id, name, **kwargs):
        """
        :param channel_id: id of the channel
        :param name: name of the channel
        """
        super().__init__(channel_id, channel_id)
        self._data = {'name': name}
        self.add(**kwargs)

    @property
    def name(self):
        return self._data['name']

    @name.setter
    def name(self, name):
        self._data['name'] = name

    def get(self, *information):
        """
        Query information on the channel

        :param information: information needed
        :return: information
        :rtype: list
        """
        output_information = list()
        for info in information:
            output_information.append(self._data.get(info))
        return output_information

    def add(self, **kwargs):
        for item, value in kwargs.items():
            if item != 'id':
                self._data[item] = value


class SlackChannelManager:
    """
    Manager for the slack channels
    """

    def __init__(self, client):
        logger.debug('Starting %s', self.__class__.__name__)
        self._client = client
        self._channels = dict()
        self._names = dict()

    async def add(self, channel):

        self._channels[channel.id] = channel
        self._names[channel.name] = channel.id

    async def get(self, id_=None, name=None):
        if not id_ and not name:
            raise ValueError
        elif name:
            id_ = self._names.get(name)
        return self._channels.get(id_)

    async def delete(self, id_=None, name=None):
        if not id_ and not name:
            raise ValueError
        elif name:
            id_ = self._names.get(name)

        channel = self._channels.pop(id_)
        del self._names[channel.name]


def retrieve_channel_id(msg):
    try:
        channel_id = msg['channel'].get('id')
    except AttributeError:
        channel_id = msg['channel']
    return channel_id


async def channel_deleted(msg, chat, facades):
    channel_id = retrieve_channel_id(msg)
    await chat.channels.delete(channel_id)


async def channel_joined(msg, chat, facades):
    channel_id = retrieve_channel_id(msg)
    channel = Channel(channel_id=channel_id, **msg['channel'])
    await chat.channels.add(channel)


async def channel_left(msg, chat, facades):
    channel_id = retrieve_channel_id(msg)
    await chat.channels.delete(channel_id)


async def channel_archive(msg, chat, facades):
    channel_id = retrieve_channel_id(msg)
    await chat.channels.delete(channel_id)


async def channel_rename(msg, chat, facades):
    channel_id = retrieve_channel_id(msg)
    channel = await chat.channels.get(channel_id)
    channel.name = msg['channel']['name']


@hookimpl
def register_slack_events():
    events = [
        {
            'name': 'channel_rename',
            'func': channel_rename,
        },
        {
            'name': 'channel_archive',
            'func': channel_archive
        },
        {
            'name': 'channel_left',
            'func': channel_left,
        },
        {
            'name': 'channel_joined',
            'func': channel_joined
        },
        {
            'name': 'channel_deleted',
            'func': channel_deleted
        },

    ]

    return events
