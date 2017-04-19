import json
import logging
import time

from .hookimpl import hookimpl

logger = logging.getLogger('sirbot.slack')


class User:
    def __init__(self, id_, raw=None, dm_id=None, last_update=None):
        """
        Class representing an user.

        :param id_: id of the user
        """

        if not raw:
            raw = dict()

        self.id = id_
        self.dm_id = dm_id
        self._raw = raw
        self._last_update = last_update

    @property
    def name(self):
        return self._raw.get('name')

    @name.setter
    def name(self, _):
        raise NotImplemented

    @property
    def admin(self):
        return self._raw.get('is_admin', False)

    @admin.setter
    def admin(self, _):
        raise NotImplemented

    @property
    def bot(self):
        return self._raw.get('is_bot', False)

    @bot.setter
    def bot(self, _):
        raise NotImplemented

    @property
    def bot_id(self):
        return self._raw.get('profile', {}).get('bot_id', '')

    @bot_id.setter
    def bot_id(self, _):
        raise NotImplemented

    @property
    def raw(self):
        return self._raw

    @raw.setter
    def raw(self, _):
        raise NotImplemented

    @property
    def send_id(self):
        return self.dm_id

    @send_id.setter
    def send_id(self, _):
        raise ValueError('Read only property')

    @property
    def last_update(self):
        return self._last_update

    @last_update.setter
    def last_update(self, _):
        raise NotImplemented


class SlackUserManager:
    """
    Manager for the user object
    """

    def __init__(self, client, facades):
        self._client = client
        self._facades = facades

    async def add(self, user):
        """
        Add an user to the UserManager

        :param user: users to add
        """
        db = self._facades.get('database')
        await db.execute(
            '''INSERT OR REPLACE INTO slack_users (id, dm_id, admin, raw, last_update)
             VALUES (?, ?, ?, ?, ?)''',
            (user.id, user.dm_id, user.admin, json.dumps(user.raw),
             user.last_update))
        await db.commit()

    async def get(self, id_, update=False, dm=False):
        """
        Return an User from the User Manager

        If the user doesn't exist query the slack API for it

        :param id_: id of the user
        :param dm: Query the direct message channel id
        :param update: query the slack api for updated user info
        :return: User
        """
        if id_.startswith('U'):
            db = self._facades.get('database')
            await db.execute('''SELECT id, dm_id, raw, last_update
                                 FROM
                                 slack_users
                                 WHERE id = ?
                              ''', (id_,))
            data = await db.fetchone()

            if data is None or data['last_update'] < (time.time() - 3600)\
                    or update:
                raw = await self._client.get_user_info(id_)
                user = User(
                    id_=data['id'],
                    raw=raw,
                    dm_id=data['dm_id'],
                    last_update=time.time())

                await self.add(user)
            else:
                user = User(
                    id_=data['id'],
                    raw=json.loads(data['raw']),
                    dm_id=data['dm_id'],
                    last_update=time.time()
                )

            if dm:
                self.ensure_dm(user, db)

            return user

    async def delete(self, id_):
        """
        Delete an user from the UserManager

        :param id_: id of the user
        :return: None
        """
        db = self._facades.get('database')
        await db.execute('''DELETE FROM slack_users WHERE id = ? ''', (id_,))
        await db.commit()

    async def ensure_user(self, id_):
        """
        Make sure the user and his direct message id are cached

        :param id_: id of the user
        :return: None
        """
        await self.get(id_, update=False)

    async def ensure_dm(self, user, db=None):
        if not db:
            db = self._facades.get('database')

        if user.send_id is None and not user.bot:
            user.dm_id = await self._client.get_user_dm_channel(user.id)
            await db.execute('''UPDATE slack_users SET dm_id = ? WHERE
                                 id = ?''', (user.dm_id, user.id))
            await db.commit()


async def user_typing(event, slack, facades):
    """
    Use the user typing event to make sure the user is in cache
    """
    await slack.users.ensure_user(id_=event.get('user'))


async def team_join(event, slack, facades):
    """
    Use the team join event to add an user to the user manager
    """
    user = User(
        id_=event['user']['id'],
        raw=event['user'],
        last_update=time.time()
    )
    await slack.users.add(user)


@hookimpl
def register_slack_events():
    events = [
        {
            'name': 'user_typing',
            'func': user_typing
        },
        {
            'name': 'team_join',
            'func': team_join
        }
    ]

    return events
