import sirbot
import pytest

async def test_bot_is_starting(loop, test_server):
    bot = sirbot.SirBot(loop=loop)
    await test_server(bot._app)
    assert bot._app == bot.app
    assert bot._incoming_queue
    assert bot._dispatcher
    assert 'incoming' in bot._tasks
