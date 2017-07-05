async def update_006(db):
    await db.execute('''ALTER TABLE slack_commands
                        RENAME TO slack_commands_tmp''')

    await db.execute('''CREATE TABLE IF NOT EXISTS slack_commands (
    ts REAL,
    to_id TEXT,
    from_id TEXT,
    command TEXT,
    text TEXT,
    raw TEXT,
    PRIMARY KEY (ts, to_id, from_id, command)
    )''')

    await db.execute('''INSERT INTO slack_commands
                        (ts, to_id, from_id, command, text, raw)
                        SELECT ts, channel, user, command, text, raw
                        FROM slack_commands_tmp''')

    await db.execute('''DROP TABLE slack_commands_tmp''')

    await db.execute('''ALTER TABLE slack_actions
                        RENAME TO slack_actions_tmp''')

    await db.execute('''CREATE TABLE IF NOT EXISTS slack_actions (
    ts REAL,
    to_id TEXT,
    from_id TEXT,
    callback_id TEXT,
    action TEXT,
    raw TEXT,
    PRIMARY KEY (ts, to_id, from_id)
    )''')

    await db.execute('''INSERT INTO slack_actions
                        (ts, to_id, from_id, callback_id, action, raw)
                        SELECT ts, channel, user, callback_id, action,
                         raw
                        FROM slack_actions_tmp''')

    await db.execute('''DROP TABLE slack_actions_tmp''')


async def update_007(db):
    await db.execute('''ALTER TABLE slack_messages
                        RENAME TO slack_messages_tmp''')

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

    await db.execute('''INSERT INTO slack_messages
                        (ts, from_id, to_id, type, mention, text, raw)
                        SELECT ts, from_id, to_id, type, mention, text, raw
                        FROM slack_messages_tmp''')

    await db.execute('''DROP TABLE slack_messages_tmp''')


async def update_008(db):

    await db.execute('''ALTER TABLE slack_users ADD
                        deleted BOOLEAN DEFAULT FALSE''')
