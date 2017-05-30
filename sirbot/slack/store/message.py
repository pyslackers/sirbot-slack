import logging

from .. import database
from ..message import SlackMessage

logger = logging.getLogger(__name__)


class MessageStore:

    def __init__(self, client, facades):

        self._client = client
        self._facades = facades

    async def thread(self, message):
        db = self._facades.get('database')
        slack = self._facades.get('slack')

        thread_ts = message.thread or message.timestamp
        raw_msgs = await database.__dict__[db.type].message.get_thread(
            db, thread_ts)

        logger.warning(raw_msgs)

        messages = list()
        for raw_msg in raw_msgs:
            message = await SlackMessage.from_raw(
                data=raw_msg['raw'],
                slack=slack
            )
            messages.append(message)
            logger.debug('----' * 20)


        return messages
