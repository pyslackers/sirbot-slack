# flake8: noqa

from . import user, channel, group, update, dispatcher, message


async def create_table(db):
    await db.execute('''CREATE TABLE IF NOT EXISTS slack_users (
    id TEXT PRIMARY KEY NOT NULL,
    dm_id TEXT,
    admin BOOLEAN DEFAULT FALSE,
    raw TEXT,
    last_update REAL,
    deleted BOOLEAN DEFAULT FALSE
    )
    ''')

    await db.execute('''CREATE TABLE IF NOT EXISTS slack_channels (
    id TEXT PRIMARY KEY NOT NULL,
    name TEXT UNIQUE,
    is_member BOOLEAN,
    is_archived BOOLEAN,
    raw TEXT,
    last_update REAL
    )
    ''')

    await db.execute('''CREATE TABLE IF NOT EXISTS slack_groups (
    id TEXT PRIMARY KEY NOT NULL,
    name TEXT UNIQUE,
    is_archived BOOLEAN,
    raw TEXT,
    last_update REAL
    )
    ''')

    await db.execute('''CREATE TABLE IF NOT EXISTS slack_messages (
    ts REAL,
    from_id TEXT,
    to_id TEXT,
    type TEXT,
    thread REAL,
    mention BOOLEAN,
    text TEXT,
    raw TEXT,
    PRIMARY KEY (ts, from_id, type)
    )
    ''')

    await db.execute('''CREATE TABLE IF NOT EXISTS slack_events (
    ts REAL,
    from_id TEXT,
    type TEXT,
    raw TEXT,
    PRIMARY KEY (ts, type)
    )''')

    await db.execute('''CREATE TABLE IF NOT EXISTS slack_commands (
    ts REAL,
    to_id TEXT,
    from_id TEXT,
    command TEXT,
    text TEXT,
    raw TEXT,
    PRIMARY KEY (ts, to_id, from_id, command)
    )''')

    await db.execute('''CREATE TABLE IF NOT EXISTS slack_actions (
    ts REAL,
    to_id TEXT,
    from_id TEXT,
    callback_id TEXT,
    action TEXT,
    raw TEXT,
    PRIMARY KEY (ts, to_id, from_id)
    )''')
