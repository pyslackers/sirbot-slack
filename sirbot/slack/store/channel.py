import json
import logging
import time

from .store import SlackStore, SlackChannelItem
from .. import database

logger = logging.getLogger(__name__)


class Channel(SlackChannelItem):
    """
    Class representing a slack channel.
    """

    def __init__(self, id_, raw=None, last_update=None):
        """
        :param id_: id_ of the channel
        """
        super().__init__(id_, raw, last_update)

    @property
    def member(self):
        return self._raw.get('is_member', False)

    @member.setter
    def member(self, _):
        raise NotImplementedError


class ChannelStore(SlackStore):
    """
    Store for the slack channels
    """

    def __init__(self, client, registry, refresh=3600):
        super().__init__(client, registry, refresh)

    async def all(self):

        channels = list()
        channels_raw = await self._client.get_channels()
        for channel_raw in channels_raw:
            channel = await self.get(channel_raw['id'])
            channels.append(channel)

        return channels

    async def get(self, id_=None, name=None, fetch=False):
        """
        Return a Channel from the Channel Manager

        :param id_: id of the channel
        :param name: name of the channel
        :param update: query the slack api for updated channel info
        :return: Channel
        """
        if not id_ and not name:
            raise SyntaxError('id_ or name must be supplied')

        db = self._registry.get('database')
        if name:
            data = await database.__dict__[db.type].channel.find_by_name(db,
                                                                         name)
        else:
            data = await database.__dict__[db.type].channel.find_by_id(db, id_)

        if data and (
                fetch or data['last_update'] < (time.time() - self._refresh)):
            channel = await self._query_by_id(data['id'])

            if channel:
                await self._add(channel, db=db)
            else:
                await self._delete(channel, db=db)

        elif data:
            channel = Channel(
                id_=data['id'],
                raw=json.loads(data['raw']),
                last_update=data['last_update']
            )
        else:
            logger.debug('Channel "%s" not found in the channel store. '
                         'Querying the Slack API', (id_ or name))
            if id_:
                channel = await self._query_by_id(id_)
            else:
                channel = await self._query_by_name(name)

            if channel:
                await self._add(channel, db=db)

        return channel

    async def _add(self, channel, db=None):
        """
        Add a channel to the channel store
        """

        if not db:
            db = self._registry.get('database')

        await database.__dict__[db.type].channel.add(db, channel)
        await db.commit()

    async def _delete(self, id_, db=None):
        """
        Delete a channel from the channel store

        :param id_: id of the channel
        :return: None
        """

        if not db:
            db = self._registry.get('database')

        await database.__dict__[db.type].channel.delete(db, id_)
        await db.commit()

    async def _query_by_id(self, id_):
        raw = await self._client.get_channel(id_)
        channel = Channel(
            id_=id_,
            raw=raw,
            last_update=time.time(),
        )

        return channel

    async def _query_by_name(self, name):
        channels = await self._client.get_channels()
        for channel in channels:
            if channel['name'] == name:
                c = await self.get(id_=channel['id'])
                return c
