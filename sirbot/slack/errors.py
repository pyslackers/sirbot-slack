from sirbot.core.errors import SirBotALotError


class SlackError(SirBotALotError):
    """Generic slack error"""


class SlackSetupError(SlackError):
    """Error during slack plugin configuration"""


class SlackClientError(SlackError):
    """Error with the slack API"""


class SlackConnectionError(SlackClientError):
    """Connection to slack server error"""


class SlackServerError(SlackClientError):
    """Internal slack server error"""


class SlackRedirectionError(SlackClientError):
    """Redirection status code"""


class SlackAPIError(SlackClientError):
    """Wrong use of slack API"""

    def __init__(self, response):
        self.ok = response.get('ok')
        self.error = response.get('error')
        self.response = response


class SlackMessageError(SlackError):
    """Generic slack message error"""


class SlackUnknownEndpoint(SlackError):
    """"""


class SlackUnknownAction(SlackUnknownEndpoint):
    """Unknown incoming action"""

    def __init__(self, action):
        self.action = action


class SlackUnknownCommand(SlackUnknownEndpoint):
    """Unknown incoming command"""

    def __init__(self, command):
        self.command = command
