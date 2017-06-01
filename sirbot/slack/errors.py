from sirbot.core.errors import MessageError, SirBotALotError


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

    def __init__(self, response):
        self.ok = response.get('ok')
        self.error = response.get('error')
        self.response = response


# class SlackChannelNotFound(SlackClientError):
#     """Channel non existent or not available to the bot"""
#
#     def __init__(self, id_=None, name=None):
#         self.id = id_
#         self.name = name


class SlackMessageError(MessageError):
    """Generic slack message error"""


class SlackUnknownEndpoint(MessageError):
    """"""


class SlackUnknownAction(SlackUnknownEndpoint):
    """Unknown incoming action"""

    def __init__(self, action):
        self.action = action


class SlackUnknownCommand(SlackUnknownEndpoint):
    """Unknown incoming command"""

    def __init__(self, command):
        self.command = command


class SlackSetupError(SirBotALotError):
    """Error during slack plugin configuration"""
