import json
import logging

logger = logging.getLogger(__name__)


async def save_incoming_action(db, action):
    await db.execute('''INSERT INTO slack_actions
                        (ts, to_id, from_id, callback_id, action, raw)
                        VALUES (?, ?, ?, ?, ?, ?)''',
                     (action.ts, action.to.id, action.frm.id,
                      action.callback_id, json.dumps(action.action),
                      json.dumps(action.raw))
                     )


async def save_incoming_command(db, command):
    await db.execute('''INSERT INTO slack_commands
                        (ts, to_id, from_id, command, text, raw) VALUES
                        (? ,?, ?, ?, ?, ?)''',
                     (command.timestamp, command.to.id,
                      command.frm.id, command.command, command.text,
                      json.dumps(command.raw))
                     )


async def save_incoming_event(db, ts, user, event):
    await db.execute('''INSERT INTO slack_events (ts, from_id, type, raw)
                        VALUES (?, ?, ?, ?)''',
                     (ts, user, event['type'], json.dumps(event))
                     )


async def save_incoming_message(db, message):
    await db.execute('''INSERT INTO slack_messages
                      (ts, from_id, to_id, type, thread, mention,
                      text, raw)
                      VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                      ''',
                     (message.timestamp, message.frm.id, message.to.id,
                      message.subtype, message.thread,
                      message.mention, message.text,
                      json.dumps(message.raw))
                     )


async def update_raw(db, message):
    await db.execute('''UPDATE slack_messages SET raw=?
                        WHERE ts=?''',
                     (json.dumps(message.raw), message.timestamp)
                     )
