import logging
import time

from .message import SlackMessage

logger = logging.getLogger('sirbot.slack')


class SlackCommand:
    def __init__(self, command, channel, user, response_url, timestamp,
                 text='', raw=None, settings=None):

        if not raw:
            raw = dict()

        if not settings:
            settings = dict()

        self.command = command
        self.channel = channel
        self.user = user
        self.response_url = response_url
        self.timestamp = timestamp
        self.text = text
        self.raw = raw
        self.settings = settings

    @classmethod
    async def from_raw(cls, data, slack, timestamp=None, settings=None):
        channel = await slack.channels.get(data['channel_id'])
        user = await slack.users.get(data['user_id'])

        if not timestamp:
            timestamp = time.time()

        return SlackCommand(
            command=data['command'],
            channel=channel,
            user=user,
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
            to=self.channel,
            response_url=self.response_url,
            response_type=response_type
        )
