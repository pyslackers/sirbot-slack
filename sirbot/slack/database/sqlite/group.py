import json
import logging

logger = logging.getLogger(__name__)


async def add(db, group):
    await db.execute(
        '''INSERT OR REPLACE INTO slack_channels (id, name, is_archived, raw,
         last_update) VALUES (?, ?, ?, ?, ?)
        ''', (
            group.id, group.name, group.archived, json.dumps(group.raw),
            group.last_update)
    )


async def delete(db, id_):
    await db.execute('''DELETE FROM slack_groups WHERE id = ?''', (id_,))


async def find(db, id_):
    await db.execute('''SELECT id, raw, last_update FROM slack_channels
                        WHERE id = ?''',
                     (id_,)
                     )
    data = await db.fetchone()
    return data
