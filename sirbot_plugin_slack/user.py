import logging

from .hookimpl import hookimpl

logger = logging.getLogger('sirbot.slack')


class User:
    def __init__(self, id_, dm_id=None, admin=False):
        """
        Class representing an user.

        :param id_: id of the user
        """
        self.id = id_
        self.dm_id = dm_id
        self.admin = admin

    @property
    def send_id(self):
        return self.dm_id

    @send_id.setter
    def send_id(self, _):
        raise ValueError('Read only property')


class SlackUserManager:
    """
    Manager for the user object
    """

    def __init__(self, client):
        self._client = client

    async def add(self, user, *, db):
        """
        Add an user to the UserManager

        :param user: users to add
        """
        await db.execute(
            '''INSERT OR REPLACE INTO slack_users (id, dm_id, admin)
             VALUES (?, ? ,?)''',
            (user.id, user.dm_id, user.admin))

    async def get(self, id_, dm=False, update=True, *, db):
        """
        Return an User from the User Manager

        If the user doesn't exist query the slack API for it

        :param id_: id of the user
        :param dm: Query the direct message channel id
        :param update: query the slack api for updated user info
        :return: User
        """
        if id_.startswith('U'):
            await db.execute('''SELECT id, dm_id, admin
                                 FROM
                                 slack_users
                                 WHERE id = ?
                              ''', (id_,))
            data = await db.fetchone()
            if data:
                user = User(id_=data['id'],
                            dm_id=data['dm_id'],
                            admin=data['admin'])
            else:
                data = await self._client.get_user_info(id_)
                user = User(id_=data['id'], dm_id=data.get('dm_channel_id'),
                            admin=data.get('is_admin', False))
                await self.add(user, db=db)

            if update:
                user.slack_data = await self._client.get_user_info(id_)

            if dm and user.send_id is None:
                user.dm_id = await self._client.get_user_dm_channel(id_)
                await db.execute('''UPDATE slack_users SET dm_id = ? WHERE
                                     id = ?''', (user.dm_id, user.id))

            return user

    async def delete(self, id_, db):
        """
        Delete an user from the UserManager

        :param id_: id of the user
        :return: None
        """
        await db.execute('''DELETE FROM slack_users WHERE id = ? ''', (id_, ))

    async def preload_user(self, id_, db):
        """
        Make sure the user and his direct message id are cached

        :param id_: id of the user
        :return: None
        """
        await self.get(id_, dm=True, update=False, db=db)


async def user_typing(event, slack, facades):
    """
    Use the user typing event to make sure the user is in cache
    """
    db = facades.get('database')
    await slack.users.preload_user(id_=event.get('user'), db=db)
    await db.commit()


async def user_change(event, slack, facades):
    """
    Use the user change event to update the user information
    """
    db = facades.get('database')
    user = await slack.users.get(event['user']['id'])
    user.add(**event['user'])
    await db.commit()


async def team_join(event, slack, facades):
    """
    Use the team join event to add an user to the user manager
    """
    db = facades.get('database')
    user = User(id_=event['user']['id'],
                admin=event['user']['is_admin'])
    await slack.users.add(user, db=db)
    await db.commit()


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
