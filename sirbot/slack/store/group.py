import json
import logging
import time

from .store import SlackStore, SlackChannelItem
from .. import database
from ..hookimpl import hookimpl

logger = logging.getLogger(__name__)


class Group(SlackChannelItem):
    """
    Class representing a slack group (private channel)
    """

    def __init__(self, id_, raw=None, last_update=None):
        super().__init__(id_, raw, last_update)


class GroupStore(SlackStore):
    """
    Store for the slack groups (private channels)
    """

    def __init__(self, client, facades, refresh=3600):
        super().__init__(client, facades, refresh)

    async def all(self):
        pass

    async def get(self, id_=None, fetch=False):

        db = self._facades.get('database')
        data = await database.__dict__[db.type].group.find(db, id_)

        if data and (
                fetch or data['last_update'] < (time.time() - self._refresh)):
            group = await self._query(id_)

            if group:
                await self._add(group, db=db)
            else:
                await self._delete(group, db=db)

        elif data:
            group = Group(
                id_=data['id'],
                raw=json.loads(data['raw']),
                last_update=data['last_update']
            )
        else:
            logger.debug('Group "%s" not found in the channel store. '
                         'Querying the Slack API', id_)

            group = await self._query(id_)

            if group:
                await self._add(group, db=db)

        return group

    async def _add(self, group, db=None):

        if not db:
            db = self._facades.get('database')

        await database.__dict__[db.type].group.add(db, group)
        await db.commit()

    async def _delete(self, id_, db=None):

        if not db:
            db = self._facades.get('database')

        await database.__dict__[db.type].group.delete(db, id_)
        await db.commit()

    async def _query(self, id_):
        raw = await self._client.get_group(id_)
        group = Group(
            id_=id_,
            raw=raw,
            last_update=time.time()
        )
        return group


async def group_archive(event, slack, _):
    """
    Use the channel archive event to delete the channel
    from the ChannelManager
    """
    await slack.groups.get(event['channel'], update=True)


async def group_joined(event, slack, _):
    """
    Use the channel joined event to update the channel status
    """
    await slack.groups.get(event['channel']['id'], update=True)


async def group_left(event, slack, _):
    """
    Use the channel left event to update the channel status
    """
    await slack.groups.get(event['channel'], update=True)


async def group_rename(event, slack, _):
    """
    User the channel rename event to update the name
    of the channel
    """
    await slack.groups.get(event['channel']['id'], update=True)


async def group_unarchive(event, slack, _):
    """
    Use the channel unarchive event to delete the channel
    from the ChannelManager
    """
    await slack.groups.get(event['channel'], update=True)


@hookimpl
def register_slack_events():
    events = [
        {
            'event': 'group_archive',
            'func': group_archive
        },
        {
            'event': 'group_joined',
            'func': group_joined
        },
        {
            'event': 'group_left',
            'func': group_left,
        },
        {
            'event': 'group_rename',
            'func': group_rename,
        },
        {
            'event': 'group_unarchive',
            'func': group_unarchive,

        }
    ]

    return events
