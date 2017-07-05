import json
import logging

logger = logging.getLogger(__name__)


async def add(db, user, dm_id=True):

    if dm_id:
        await db.execute(
            '''INSERT OR REPLACE INTO slack_users
             (id, dm_id, admin, raw, last_update, deleted)
             VALUES (?, ?, ?, ?, ?, ?)''',
            (user.id, user.dm_id, user.admin, json.dumps(user.raw),
             user.last_update, user.deleted))
    else:
        await db.execute(
            '''INSERT OR REPLACE INTO slack_users
             (dm_id, id, admin, raw, last_update, deleted)
             VALUES (
                (SELECT dm_id FROM slack_users WHERE id=?),
                ?, ?, ?, ?, ?
             )'''.format(user.id),
            (user.id, user.id, user.admin, json.dumps(user.raw),
             user.last_update, user.deleted))


async def add_multiple(db, users):
    for user in users:
        await add(db, user)


async def delete(db, id_):
    await db.execute('''DELETE FROM slack_users WHERE id = ? ''', (id_,))


async def get_all(db, deleted=False):
    filter_ = ''
    if not deleted:
        filter_ = 'WHERE deleted=0'

    await db.execute('''SELECT * FROM slack_users {filter}'''.format(
        filter=filter_))
    users = await db.fetchall()
    return users


async def find(db, id_):
    await db.execute('''SELECT id, dm_id, raw, last_update, deleted
                        FROM slack_users WHERE id = ?''',
                     (id_,)
                     )
    data = await db.fetchone()
    return data


async def update_dm_id(db, id_, dm_id):
    await db.execute('''UPDATE slack_users SET dm_id = ? WHERE
                         id = ?''', (dm_id, id_))
