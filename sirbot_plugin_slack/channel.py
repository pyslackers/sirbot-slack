import logging

from sirbot.receiver import Receiver

from .hookimpl import hookimpl

logger = logging.getLogger('sirbot.slack')


class Channel(Receiver):
    """
    Class representing a slack channel.
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
        """
        name of the channel
        """
        return self._data['name']

    @name.setter
    def name(self, name):
        raise ValueError('Readonly property')

    @property
    def members(self):
        """
        Id of the users in the channels
        :return: list of users id
        :rtype: list
        """
        return self._data['members']

    @members.setter
    def members(self, members):
        raise ValueError('Readonly property')

    @property
    def is_member(self):
        """
        Boolean if the bot is member of the channel
        """
        return self._data['is_members']

    @is_member.setter
    def is_member(self, is_member):
        raise ValueError('Readonly property')

    @property
    def is_archive(self):
        return self._data['is_archive']

    @is_archive.setter
    def is_archive(self, is_archive):
        raise ValueError('Readonly property')

    def get(self, information):
        """
        Query information on the channel

        :param information: information needed
        :return: information
        """
        return self._data.get(information)

    def add(self, **kwargs):
        """
        Add information to the channel

        :param kwargs:
        :return:
        """
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
        """
        Add a channel to the channel manager
        """
        self._channels[channel.id] = channel
        self._names[channel.name] = channel.id

    async def get(self, id_=None, name=None, update=True):
        """
        Return a Channel from the Channel Manager

        :param id_: id of the channel
        :param name: name of the channel
        :param update: query the slack api for updated channel info
        :return: Channel
        """
        if not id_ and not name:
            raise SyntaxError
        elif name:
            id_ = self._names.get(name)

        channel = self._channels.get(id_)
        if not channel:
            logger.debug('Channel not found in the channel manager'
                         'Querying the Slack API')
            if id_:
                channel = Channel(channel_id=id_,
                                  **(await self._client.get_channel_info(
                                      id_)))
            else:
                _, channels = self._client.get_channels()
                for channel in channels:
                    if channel.name == name:
                        return channel
                return

        elif update and channel:
            channel.add(**(await self._client.get_channel_info(id_)))

        return channel

    async def delete(self, id_=None, name=None):
        """
        Delete a channel from the channel manager

        :param id_: id of the channel
        :param name: name of the channel
        :return: None
        """
        if not id_ and not name:
            raise SyntaxError
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


async def channel_archive(event, slack, facades):
    """
    Use the channel archive event to delete the channel
    from the ChannelManager
    """
    channel_id = retrieve_channel_id(event)
    channel = await slack.channels.get(channel_id, update=False)
    channel._data['is_archive'] = True


async def channel_created(event, slack, facades):
    """
    Use the channel created event to add the channel
    to the ChannelManager
    """
    channel_id = retrieve_channel_id(event)
    channel = Channel(channel_id=channel_id, **event['channel'])
    await slack.channels.add(channel)


async def channel_deleted(event, slack, facades):
    """
    Use the channel delete event to delete the channel
    from the ChannelManager
    """
    channel_id = retrieve_channel_id(event)
    await slack.channels.delete(channel_id)


async def channel_joined(event, slack, facades):
    """
    Use the channel joined event to update the channel status
    """
    channel_id = retrieve_channel_id(event)
    channel = await slack.channels.get(channel_id, update=False)
    channel._data['is_member'] = True


async def channel_left(event, slack, facades):
    """
    Use the channel left event to update the channel status
    """
    channel_id = retrieve_channel_id(event)
    channel = await slack.channels.get(channel_id, update=False)
    channel._data['is_member'] = False


async def channel_rename(event, slack, facades):
    """
    User the channel rename event to update the name
    of the channel
    """
    channel_id = retrieve_channel_id(event)
    channel = await slack.channels.get(channel_id, update=False)
    old_name = channel.name
    channel._data['name'] = event['channel']['name']
    slack.channels._names[channel.name] = channel.id
    del slack.channels._names[old_name]


async def channel_unarchive(event, slack, facades):
    """
    Use the channel unarchive event to delete the channel
    from the ChannelManager
    """
    channel_id = retrieve_channel_id(event)
    channel = await slack.channels.get(channel_id, update=False)
    channel._data['is_archive'] = False


@hookimpl
def register_slack_events():
    events = [
        {
            'name': 'channel_archive',
            'func': channel_archive
        },
        {
            'name': 'channel_created',
            'func': channel_created
        },
        {
            'name': 'channel_deleted',
            'func': channel_deleted
        },
        {
            'name': 'channel_joined',
            'func': channel_joined
        },
        {
            'name': 'channel_left',
            'func': channel_left,
        },
        {
            'name': 'channel_rename',
            'func': channel_rename,
        },
        {
            'name': 'channel_unarchive',
            'func': channel_unarchive,

        }
    ]

    return events
