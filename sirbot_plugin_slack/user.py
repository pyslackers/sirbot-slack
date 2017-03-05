import logging
import time

from .hookimpl import hookimpl

logger = logging.getLogger('sirbot.slack')


class User:
    def __init__(self, id_=None, **kwargs):
        """
        Class representing an user.

        :param id_: id of the user
        :param name: name of the user
        """
        self.id = id_
        self._data = dict()
        self.add(**kwargs)
        self.last_seen = time.time()

    def add(self, **kwargs):
        """
        Add information to an user
        """
        for item, value in kwargs.items():
            if item != 'id':
                self._data[item] = value

    @property
    def send_id(self):
        """
        id where the message need to be sent to reach the user
        """
        return self._data.get('dm_channel_id')

    @send_id.setter
    def send_id(self, send_id):
        self._data['dm_channel_id'] = send_id

    @property
    def name(self):
        """
        Name of the user
        """
        return self._data['profile']['real_name']

    @name.setter
    def name(self, _):
        raise ValueError('Readonly property')

    @property
    def is_admin(self):
        """
        Boolean is the user an admin of the team
        """
        return self._data['is_admin']

    @is_admin.setter
    def is_admin(self, _):
        raise ValueError('Readonly property')

    @property
    def profile(self):
        """
        Profile information of the user
        """
        return self._data['profile']

    @profile.setter
    def profile(self, profile):
        self._data['profile'] = profile

    def __str__(self):
        return self.id


class SlackUserManager:
    """
    Manager for the user object
    """

    def __init__(self, client):
        self._client = client
        self._users = dict()

    async def add(self, user):
        """
        Add an user to the UserManager

        :param user: users to add
        """
        self._users[user.id] = user

    async def get(self, id_=None, dm=False, update=True):
        """
        Return an User from the User Manager

        If the user doesn't exist query the slack API for it

        :param id_: id of the user
        :param dm: Query the direct message channel id
        :param update: query the slack api for updated user info
        :return: User
        """
        if id_.startswith('U'):
            user = self._users.get(id_)

            if user is None:
                user = await self._client.get_user_info(id_)
                user = User(user['id'], **user)
                await self.add(user)
            elif update:
                user.add(**(await self._client.get_user_info(id_)))

            if dm and user.send_id is None:
                dm_id = await self._client.get_user_dm_channel(id_)
                user.send_id = dm_id

            return user

    async def delete(self, id_=None):
        """
        Delete an user from the UserManager

        :param id_: id of the user
        :return: None
        """
        del self._users[id_]

    async def preload_user(self, id_):
        """
        Make sure the user and his direct message id are cached

        :param id_: id of the user
        :return: None
        """
        await self.get(id_, dm=True, update=False)


async def user_typing(event, slack, facades):
    """
    Use the user typing event to make sure the user is in cache
    """
    await slack.users.preload_user(id_=event.get('user'))


async def user_change(event, slack, facades):
    """
    Use the user change event to update the user information
    """
    user = await slack.users.get(event['user']['id'])
    user.update(**event['user'])


async def team_join(event, slack, facades):
    """
    Use the team join event to add an user to the user manager
    """
    await slack.users.add(User(**event['user']))


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
        },
        {
            'name': 'team_join',
            'func': team_join
        }
    ]

    return events
