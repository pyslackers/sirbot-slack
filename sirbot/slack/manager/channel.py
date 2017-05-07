import json
import logging
import time

from ..hookimpl import hookimpl
from ..errors import SlackAPIError, SlackChannelNotFound

logger = logging.getLogger(__name__)


class Channel:
    """
    Class representing a slack channel.
    """

    def __init__(self, id_, raw=None, last_update=None):
        """
        :param name: name of the channel
        """

        if not raw:
            raw = dict()

        self.id = id_
        self._raw = raw
        self._last_update = last_update

    @property
    def name(self):
        return self._raw.get('name')

    @name.setter
    def name(self, _):
        raise NotImplementedError

    @property
    def member(self):
        return self._raw.get('is_member', False)

    @member.setter
    def member(self, _):
        raise NotImplementedError

    @property
    def members(self):
        return self._raw.get('members')

    @members.setter
    def members(self, _):
        raise NotImplementedError

    @property
    def topic(self):
        return self._raw.get('topic')

    @topic.setter
    def topic(self, _):
        raise NotImplementedError

    @property
    def purpose(self):
        return self._raw.get('purpose')

    @purpose.setter
    def purpose(self, _):
        raise NotImplementedError

    @property
    def archived(self):
        return self._raw.get('is_archived', False)

    @archived.setter
    def archived(self, _):
        raise NotImplementedError

    @property
    def raw(self):
        return self._raw

    @raw.setter
    def raw(self, _):
        raise NotImplementedError

    @property
    def send_id(self):
        return self.id

    @send_id.setter
    def send_id(self, _):
        raise NotImplementedError

    @property
    def last_update(self):
        return self._last_update

    @last_update.setter
    def last_update(self, _):
        raise NotImplementedError


class SlackChannelManager:
    """
    Manager for the slack channels
    """

    def __init__(self, client, facades, refresh):
        self._client = client
        self._facades = facades
        self._refresh = refresh
        self._channels = dict()

    async def all(self):

        channels = list()
        channels_raw = await self._client.get_channels()
        for channel_raw in channels_raw:
            channel = await self.get(channel_raw['id'])
            channels.append(channel)

        return channels

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
            data = await self._get_by_name(name, db)
        elif id_:
            data = await self._get_by_id(id_, db)

        if data and (
                update or data['last_update'] < (time.time() - self._refresh)
        ):
            data = await self._update(data)
            channel = Channel(
                id_=data['id'],
                raw=data,
                last_update=time.time()
            )
            await self.add(channel, db=db)
            return channel
        elif data:
            channel = Channel(
                id_=data['id'],
                raw=json.loads(data['raw']),
                last_update=data['last_update']
            )
            return channel
        else:
            logger.debug('Channel "%s" not found in the channel manager. '
                         'Querying the Slack API', (id_ or name))
            if id_:
                data = await self._find_by_id(id_)
            else:
                data = await self._client.find_channel(name)

            if not data:
                raise SlackChannelNotFound(id_, name)

            channel = Channel(
                id_=data['id'],
                raw=data,
                last_update=time.time()
            )
            await self.add(channel, db=db)
            return channel

    async def _find_by_id(self, id_):
        if id_.startswith('C'):
            data = await self._client.get_channel(id_)
        else:
            try:
                data = await self._client.get_group_info(id_)
            except SlackAPIError as e:
                if e.error == 'channel_not_found':
                    data = None
                    logger.debug(
                        'Group "%s" not found in available groups', id_)
                else:
                    raise

        return data

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

    async def add(self, channel, *, db=None):
        """
        Add a channel to the channel manager
        """
        db = db or self._facades.get('database')
        await db.execute(
            '''INSERT OR REPLACE INTO slack_channels (id, name, is_member,
             is_archived, raw, last_update) VALUES (?, ?, ?, ?, ?, ?)''',
            (channel.id, channel.name, channel.member, channel.archived,
             json.dumps(channel.raw), channel.last_update)
        )
        await db.commit()

    async def _get_by_name(self, name, db):
        await db.execute('''SELECT id, raw, last_update FROM slack_channels
                            WHERE name = ?''',
                         (name,)
                         )
        data = await db.fetchone()
        return data

    async def _get_by_id(self, id_, db):
        await db.execute('''SELECT id, raw, last_update FROM slack_channels
                            WHERE id = ?''',
                         (id_,)
                         )
        data = await db.fetchone()
        return data

    async def _update(self, data):

        if data['id'].startswith('C'):
            data = await self._client.get_channel(data['id'])
        else:
            data = dict()

        return data


async def channel_archive(event, slack, facades):
    """
    Use the channel archive event to delete the channel
    from the ChannelManager
    """
    await slack.channels.get(event['channel'], update=True)


async def channel_created(event, slack, facades):
    """
    Use the channel created event to add the channel
    to the ChannelManager
    """
    await slack.channels.get(event['channel']['id'])


async def channel_deleted(event, slack, facades):
    """
    Use the channel delete event to delete the channel
    from the ChannelManager
    """
    await slack.channels.delete(event['channel'])


async def channel_joined(event, slack, facades):
    """
    Use the channel joined event to update the channel status
    """
    channel = Channel(
        id_=event['channel']['id'],
        raw=event['channel'],
        last_update=time.time()
    )
    await slack.channels.add(channel)


async def channel_left(event, slack, facades):
    """
    Use the channel left event to update the channel status
    """
    await slack.channels.get(event['channel'], update=True)


async def channel_rename(event, slack, facades):
    """
    User the channel rename event to update the name
    of the channel
    """
    await slack.channels.get(event['channel']['id'], update=True)


async def channel_unarchive(event, slack, facades):
    """
    Use the channel unarchive event to delete the channel
    from the ChannelManager
    """
    await slack.channels.get(event['channel'], update=True)


@hookimpl
def register_slack_events():
    events = [
        {
            'event': 'channel_archive',
            'func': channel_archive
        },
        {
            'event': 'channel_created',
            'func': channel_created
        },
        {
            'event': 'channel_deleted',
            'func': channel_deleted
        },
        {
            'event': 'channel_joined',
            'func': channel_joined
        },
        {
            'event': 'channel_left',
            'func': channel_left,
        },
        {
            'event': 'channel_rename',
            'func': channel_rename,
        },
        {
            'event': 'channel_unarchive',
            'func': channel_unarchive,

        }
    ]

    return events
