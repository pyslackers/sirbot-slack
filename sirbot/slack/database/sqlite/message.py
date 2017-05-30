import json

async def get_thread(db, thread_ts):

    await db.execute('''SELECT raw FROM slack_messages
                        WHERE thread = ?
                        ORDER BY ts DESC''', (thread_ts,))

    messages = await db.fetchall()
    data = [{'raw': json.loads(message['raw'])
             for message in messages}]

    return data
