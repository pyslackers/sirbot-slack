from sirbot.errors import MessageError, SirBotALotError


class SlackClientError(SirBotALotError):
    """Generic slack client error"""


class SlackConnectionError(SlackClientError):
    """Connection to slack server error"""


class SlackServerError(SlackClientError):
    """Internal slack server error"""


class SlackRedirectionError(SlackClientError):
    """Redirection status code"""


class SlackAPIError(SlackClientError):
    """Wrong use of slack API"""


class SlackMessageError(MessageError):
    """Generic slack message error"""
