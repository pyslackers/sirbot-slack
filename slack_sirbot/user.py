import logging
import time

from sirbot.receiver import Receiver

from .hookimpl import hookimpl

logger = logging.getLogger('sirbot.slack')


class User(Receiver):
    """
    Class representing an user.
    """
    def __init__(self, user_id=None, **kwargs):
        """
        :param user_id: id of the user
        """
        self._data = dict()
        self.update(**kwargs)
        self.last_seen = time.time()
        super().__init__(user_id, None)

    def update(self, **kwargs):
        for item, value in kwargs.items():
            if item != 'id':
                self._data[item] = value

    @property
    def send_id(self):
        return self._data['dm_channel_id']

    @send_id.setter
    def send_id(self, send_id):
        self._data['dm_channel_id'] = send_id

    def name(self):
        return self._data['profile']['real_name']

    def __str__(self):
        return self.id


class SlackUserManager:
    """
    Manager for the user object
    """

    def __init__(self, client):
        logger.debug('Starting %s', self.__class__.__name__)
        self._client = client
        self._users = dict()

    async def add(self, user):
        """
        Add an user to the UserManager

        :param users: users to add
        """
        self._users[user.id] = user

    async def get(self, id_=None, dm=False):
        """
        Return an User from the User Manager

        If the user doesn't exist query the slack API for it

        :param id_: id of the user
        :param dm: Query the direct message channel id
        :return: User
        """
        if id_.startswith('U'):
            user = self._users.get(id_)

            if user is None:
                user = await self._client.get_user_info(id_)
                user = User(user['id'], **user)
                await self.add(user)

            if dm and user.send_id is None:
                dm_id = await self._client.get_user_dm_channel(id_)
                user.send_id = dm_id

            return user

    async def preload_user(self, id_):
        await self.get(id_, dm=True)


async def user_typing(msg, chat, facades):
    await chat.users.preload_user(id_=msg.get('user'))


async def user_change(msg, chat, facades):
    user = await chat.users.get(msg['user']['id'])
    user.update(**msg['user'])


@hookimpl
def register_slack_events():
    events = [
        {
            'name': 'user_typing',
            'func': user_typing
        },
        {
            'name': 'user_change',
            'func': user_change
        }
    ]

    return events
