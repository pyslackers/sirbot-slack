import logging
import time

from .message import SlackMessage

logger = logging.getLogger('sirbot.slack')


class SlackCommand:
    def __init__(self, command, frm, to, response_url, timestamp,
                 text='', raw=None, settings=None):

        if not raw:
            raw = dict()

        if not settings:
            settings = dict()

        self.command = command
        self.frm = frm
        self.to = to
        self.response_url = response_url
        self.timestamp = timestamp
        self.text = text
        self.raw = raw
        self.settings = settings

    @classmethod
    async def from_raw(cls, data, slack, timestamp=None, settings=None):

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
            settings=settings,
        )

    def response(self):

        if self.settings.get('public'):
            response_type = 'in_channel'
        else:
            response_type = 'ephemeral'

        return SlackMessage(
            to=self.to,
            response_url=self.response_url,
            response_type=response_type
        )
