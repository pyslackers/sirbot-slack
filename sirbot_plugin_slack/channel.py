import logging

from .hookimpl import hookimpl

logger = logging.getLogger('sirbot.slack')


class Channel:
    """
    Class representing a slack channel.
    """

    def __init__(self, id_, name, is_member=False, is_archived=False):
        """
        :param name: name of the channel
        """
        self.id = id_
        self.name = name
        self.is_member = is_member
        self.is_archived = is_archived

    @property
    def send_id(self):
        return self.id

    @send_id.setter
    def send_id(self, _):
        raise ValueError('Read only property')


class SlackChannelManager:
    """
    Manager for the slack channels
    """

    def __init__(self, client, facades):
        self._client = client
        self._facades = facades
        self._channels = dict()
        self._names = dict()

    async def add(self, channel):
        """
        Add a channel to the channel manager
        """
        db = self._facades.get('database')
        await db.execute(
            '''INSERT OR REPLACE INTO slack_channels (id, name, is_member,
             is_archived) VALUES (?, ?, ?, ?)''', (channel.id,
                                                   channel.name,
                                                   channel.is_member,
                                                   channel.is_archived)
        )
        await db.commit()

    async def get(self, id_=None, name=None, update=False):
        """
        Return a Channel from the Channel Manager

        :param id_: id of the channel
        :param name: name of the channel
        :param update: query the slack api for updated channel info
        :return: Channel
        """
        data = dict()
        if not id_ and not name:
            raise SyntaxError('id_ or name must be supplied')

        db = self._facades.get('database')
        if name:
            await db.execute('''SELECT id, name, is_member, is_archived FROM
                                 slack_channels WHERE name = ?''', (name,)
                             )
            data = await db.fetchone()
        elif id_:
            await db.execute('''SELECT id, name, is_member, is_archived FROM
                                 slack_channels WHERE id = ?''', (id_,)
                             )
            data = await db.fetchone()

        if not data:
            logger.debug('Channel not found in the channel manager. '
                         'Querying the Slack API')
            if id_:
                data = await self._client.get_channel_info(id_)
                channel = Channel(id_=id_,
                                  name=data['name'],
                                  is_member=data['is_member'],
                                  is_archived=data['is_archived'])
                self.add(channel)
                return channel
            else:
                _, channels = self._client.get_channels()
                for channel in channels:
                    if channel.name == name:
                        self.add(channel)
                        return channel
                return
        else:
            channel = Channel(id_=data['id'],
                              name=data['name'],
                              is_member=data['is_member'],
                              is_archived=data['is_archived'])

        if update:
            data = await self._client.get_channel_info(id_)
            channel.slack_data = data

        return channel

    async def delete(self, id_):
        """
        Delete a channel from the channel manager

        :param id_: id of the channel
        :param name: name of the channel
        :return: None
        """
        db = self._facades.get('database')
        await db.execute('''DELETE FROM slack_channels WHERE id = ?
                          ''', (id_,))
        await db.commit()


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
    db = facades.get('database')
    channel_id = retrieve_channel_id(event)
    await db.execute('''UPDATE slack_channels SET is_archived = 1 WHERE
                      id = ?''', (channel_id, ))
    await db.commit()


async def channel_created(event, slack, facades):
    """
    Use the channel created event to add the channel
    to the ChannelManager
    """
    channel_id = retrieve_channel_id(event)
    channel = Channel(
        id_=channel_id,
        name=event['channel']['name'],
        is_member=event['channel']['is_member'],
        is_archived=event['channel']['is_archived']
    )
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
    db = facades.get('database')
    channel_id = retrieve_channel_id(event)
    await db.execute('''UPDATE slack_channels SET is_member = 1 WHERE
                      id = ?''', (channel_id,))
    await db.commit()


async def channel_left(event, slack, facades):
    """
    Use the channel left event to update the channel status
    """
    db = facades.get('database')
    channel_id = retrieve_channel_id(event)
    await db.execute('''UPDATE slack_channels SET is_member = 0 WHERE
                      id = ?''', (channel_id,))
    await db.commit()


async def channel_rename(event, slack, facades):
    """
    User the channel rename event to update the name
    of the channel
    """
    db = facades.get('database')
    channel_id = retrieve_channel_id(event)
    await db.execute('''UPDATE slack_channels SET name = ? WHERE id = ?
                      ''', (event['channel']['name'], channel_id))
    await db.commit()


async def channel_unarchive(event, slack, facades):
    """
    Use the channel unarchive event to delete the channel
    from the ChannelManager
    """
    db = facades.get('database')
    channel_id = retrieve_channel_id(event)
    await db.execute('''UPDATE slack_channels SET is_archived = 0 WHERE
                      id = ?''', (channel_id,))
    await db.commit()


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
