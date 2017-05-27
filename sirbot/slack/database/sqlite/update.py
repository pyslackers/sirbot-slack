async def update_005(db):
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
