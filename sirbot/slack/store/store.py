import logging

logger = logging.getLogger(__name__)


class SlackStore:

    def __init__(self, client, registry, refresh=3600):
        self._client = client
        self._registry = registry
        self._refresh = refresh

    async def all(self):
        pass

    async def get(self, id_, update=False):
        pass

    async def _add(self, item):
        pass

    async def _delete(self, id_):
        pass


class SlackItem:

    def __init__(self, id_, raw=None, last_update=None):

        if not raw:
            raw = dict()

        self.id = id_
        self._raw = raw
        self._last_update = last_update

    @property
    def name(self):
        return self._raw.get('name')

    @name.setter
    def name(self, _):
        raise NotImplementedError

    @property
    def send_id(self):
        return self.id

    @send_id.setter
    def send_id(self, _):
        raise NotImplementedError

    @property
    def raw(self):
        return self._raw

    @raw.setter
    def raw(self, _):
        raise NotImplementedError

    @property
    def last_update(self):
        return self._last_update

    @last_update.setter
    def last_update(self, _):
        raise NotImplementedError


class SlackChannelItem(SlackItem):

    def __init__(self, id_, raw=None, last_update=None):
        super().__init__(id_, raw, last_update)

    @property
    def members(self):
        return self._raw.get('members')

    @members.setter
    def members(self, _):
        raise NotImplementedError

    @property
    def topic(self):
        return self._raw.get('topic')

    @topic.setter
    def topic(self, _):
        raise NotImplementedError

    @property
    def purpose(self):
        return self._raw.get('purpose')

    @purpose.setter
    def purpose(self, _):
        raise NotImplementedError

    @property
    def archived(self):
        return self._raw.get('is_archived', False)

    @archived.setter
    def archived(self, _):
        raise NotImplementedError
