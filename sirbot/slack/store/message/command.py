import logging
import time

from .message import SlackMessage

logger = logging.getLogger('sirbot.slack')


class SlackCommand:
    def __init__(self, command, frm, to, response_url, timestamp,
                 text='', raw=None):

        if not raw:
            raw = dict()

        self.command = command
        self.frm = frm
        self.to = to
        self.response_url = response_url
        self.timestamp = timestamp
        self.text = text
        self.raw = raw

    @classmethod
    async def from_raw(cls, data, slack, timestamp=None):

        frm = await slack.users.get(data['user_id'])
        if data['channel_id'].startswith('C'):
            to = await slack.channels.get(data['channel_id'])
        elif data['channel_id'].startswith('G'):
            to = await slack.groups.get(data['channel_id'])
        else:
            to = frm

        if not timestamp:
            timestamp = time.time()

        return SlackCommand(
            command=data['command'],
            to=to,
            frm=frm,
            response_url=data['response_url'],
            text=data['text'],
            timestamp=timestamp,
            raw=data,
        )

    def response(self, type_='in_channel'):

        if type_ not in ('in_channel', 'ephemeral'):
            raise ValueError('''response type must be one of 'in_channel',
             'ephemeral' ''')

        return SlackMessage(
            to=self.to,
            response_url=self.response_url,
            response_type=type_
        )
