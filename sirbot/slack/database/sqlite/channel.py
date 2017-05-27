import json
import logging

logger = logging.getLogger(__name__)


async def delete(db, id_):
    await db.execute('''DELETE FROM slack_channels WHERE id = ?''', (id_,))


async def add(db, channel):
    await db.execute(
        '''INSERT OR REPLACE INTO slack_channels (id, name,
           is_member, is_archived, raw, last_update) VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            channel.id, channel.name, channel.member, channel.archived,
            json.dumps(channel.raw), channel.last_update)
    )


async def find_by_id(db, id_):
    await db.execute('''SELECT id, raw, last_update FROM slack_channels
                        WHERE id = ?''',
                     (id_,)
                     )
    data = await db.fetchone()
    return data


async def find_by_name(db, name):
    await db.execute('''SELECT id, raw, last_update FROM slack_channels
                        WHERE name = ?''',
                     (name,)
                     )
    data = await db.fetchone()
    return data
