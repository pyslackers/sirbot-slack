import json
import logging

logger = logging.getLogger(__name__)


async def get_thread(db, thread_ts, limit):
    if limit:
        await db.execute('''SELECT raw FROM slack_messages
                            WHERE thread=?
                            ORDER BY ts DESC LIMIT ?''', (thread_ts, limit))
    else:
        await db.execute('''SELECT raw FROM slack_messages
                            WHERE thread=?
                            ORDER BY ts DESC''', (thread_ts,))

    messages = await db.fetchall()
    data = [{'raw': json.loads(message['raw'])} for message in messages]
    return data


async def get_channel(db, channel_id, since, until):
    await db.execute('''SELECT raw FROM slack_messages WHERE channel=?
                        AND ts>? AND ts<?
                        ORDER BY ts DESC''', (channel_id, since, until))

    messages = await db.fetchall()
    data = [{'raw': json.loads(message['raw'])} for message in messages]
    return data
