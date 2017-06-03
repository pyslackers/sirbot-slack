import logging

from .message import SlackMessage

logger = logging.getLogger('sirbot.slack')


class SlackAction:
    def __init__(self, callback_id, to, frm, response_url, action, ts,
                 message_ts, raw=None, settings=None):

        if not raw:
            raw = dict()

        if not settings:
            settings = dict()

        self.callback_id = callback_id
        self.frm = frm
        self.to = to
        self.ts = ts
        self.response_url = response_url
        self.action = action
        self.raw = raw
        self.message_ts = message_ts
        self.settings = settings

    def response(self):
        return SlackMessage(
            to=self.to,
            response_url=self.response_url,
        )

    @classmethod
    async def from_raw(cls, data, slack, settings=None):

        frm = await slack.users.get(data['user']['id'])
        if data['channel']['id'].startswith('C'):
            to = await slack.channels.get(data['channel']['id'])
        elif data['channel']['id'].startswith('G'):
            to = await slack.groups.get(data['channel']['id'])
        else:
            to = frm

        return SlackAction(
            callback_id=data['callback_id'],
            to=to,
            frm=frm,
            response_url=data['response_url'],
            action=data['actions'][0],
            ts=data['action_ts'],
            message_ts=data['message_ts'],
            raw=data,
            settings=settings
        )
