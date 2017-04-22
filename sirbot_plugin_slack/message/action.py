import logging

from sirbot_plugin_slack.message import SlackMessage

logger = logging.getLogger('sirbot.slack')


class SlackAction:
    def __init__(self, callback_id, channel, user, response_url, action, ts,
                 message_ts, raw=None, settings=None):

        if not raw:
            raw = dict()

        if not settings:
            settings = dict()

        self.callback_id = callback_id
        self.channel = channel
        self.user = user
        self.ts = ts
        self.response_url = response_url
        self.action = action
        self.raw = raw
        self.message_ts = message_ts
        self.settings = settings

    def response(self):
        return SlackMessage(
            to=self.channel,
            response_url=self.response_url,
            timestamp=self.message_ts
        )

    @classmethod
    async def from_raw(cls, data, slack, settings=None):
        channel = await slack.channels.get(data['channel']['id'])
        user = await slack.users.get(data['user']['id'])

        return SlackAction(
            callback_id=data['callback_id'],
            channel=channel,
            user=user,
            response_url=data['response_url'],
            action=data['actions'][0],
            ts=data['action_ts'],
            message_ts=data['message_ts'],
            raw=data,
            settings=settings
        )
