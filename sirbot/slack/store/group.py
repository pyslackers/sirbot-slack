import json
import logging
import time

from .store import SlackStore, SlackChannelItem
from .. import database

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

    def __init__(self, client, registry, refresh=3600):
        super().__init__(client, registry, refresh)

    async def all(self):
        pass

    async def get(self, id_=None, fetch=False):

        db = self._registry.get('database')
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
            db = self._registry.get('database')

        await database.__dict__[db.type].group.add(db, group)
        await db.commit()

    async def _delete(self, id_, db=None):

        if not db:
            db = self._registry.get('database')

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
