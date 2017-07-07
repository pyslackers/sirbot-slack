==================
Bot users tutorial
==================

Create the bot
--------------

First we need a bot user to create one go to this `page`_ and enter your bot
username. Once this is done you will be provided with an ``API Token``
(starting with ``xoxb``).

This is your :ref:`authentification` token.

.. _page: https://my.slack.com/services/new/bot

Installation
------------

Next step will be to install `Sir-bot-a-lot`_ in your virtual environment.
First download all the necessary packages.

.. code-block:: console

    $ git clone git://github.com/pyslackers/sir-bot-a-lot
    $ git clone git://github.com/pyslackers/sirbot-plugins
    $ git clone git://github.com/pyslackers/sirbot-slack


Then make sure to activate your virtual environment and install the packages.

.. code-block:: console

    $ source .env/bin/activate
    $ pip install sir-bot-a-lot/
    $ pip install sirbot-plugins/
    $ pip install sirbot-slack/

Configuration
-------------

`Sir-bot-a-lot`_ expect your ``API Token`` to be an environment variable. The
easiest way to set it is:

.. code-block:: console

    $ export SIRBOT_SLACK_BOT_TOKEN=xoxb-0123456789

Except the tokens all configuration takes place in the yaml configuration file.
It can be located from anywhere in your file system you only need to pass the
path as the ``--config`` argument when starting `Sir-bot-a-lot`_.

.. code-block:: yaml

    sirbot:
        plugins:                    # Plugins we want to use
            - sirbot.plugins.sqlite # Required but the slack plugins
            - sirbot.slack

    slack:
        priority: 20                # We make sure the slack plugin start after the sqlite plugin
        rtm: true                   # We want to connect to the rtm API

    sqlite:
        file: ':memory:'            # The database will only be stored in memory (default)


Now that we have configured `Sir-bot-a-lot`_ we can start it with:

.. code-block:: console

    (.env) $ sirbot -c path/to/configuration/file

You should now see some logs in your terminal and hopefully the presence status
of your bot will turn green. By default your bot will react to mention
(``@mybot``) with the ``:robot_face:`` emoji.

Responding to message
---------------------

In order to customize the behavior of your bot you need to write your very own
plugin. You can look at the one for the `python developers slack community`_
over `here`_.

For that create a new file named ``my_awesome_plugin.py`` with this small
example plugin that respond ``I'm alive!`` when someone send the message
``@mybot hello`` in a channel your bot is in.

.. code-block:: python

    import re

    from sirbot.core import hookimpl, Plugin

    @hookimpl
    def plugins(loop):
        return MyAwesomePlugin(loop)

    class MyAwesomePlugin(Plugin):

        __version__ = '0.0.1'
        __name__ = 'my_awesome_plugin'

        def __init__(self, loop):
            self._loop = loop
            self._started = True
            self._registry = None

        async def configure(self, config, router, session, registry):
            self._registry = registry

        async def start(self):

            # Get the slack plugin api to add new message endpoints
            slack = self._registry.get('slack')

            # Register a new endpoints for message matching the 'hello' regex. We
            # also had the 're.IGNORECASE' flag to also match 'Hello', 'heLLo' etc
            # and the we set the mention parameter to True so it will only react
            # when someone @ him or talk in a direct message.
            slack.add_message('hello',
                              self.my_message_response,
                              flags=re.IGNORECASE,
                              mention=True)

            # Our plugin is successfully started
            self._started = True

        @property
        def started(self):
            return self._started

        async def my_message_response(self, message, slack, registry, match)

            response = message.response()       # Create a response from the incoming message
            response.text = '''I'm alive!'''    # Set the response text

            await slack.send(response)          # Send the response

Now that you have created your plugin we need to tell `Sir-bot-a-lot` to load
it. For that we add the import path of your file to the list of plugins.

.. code-block:: yaml

    sirbot:
        plugins:
            - sirbot.plugins
            - sirbot.slack
            - my_awesome_plugin

And since we ask for the slack plugin api in the configuration we need to edit
the configuration file to make sure ``my_awesome_plugin`` start after slack.
For this we will add the following snippet at the end:

.. code-block:: yaml

    my_awesome_plugin:
        priority: 1

You are now the proud possessor of an awesome slack bot !

.. _Sir-bot-a-lot: http://sir-bot-a-lot.readthedocs.io/en/latest/
.. _here: https://github.com/pyslackers/sirbot-pythondev

Help
----

For additionnal help you can `open an issue`_ or join us in the
``community_projects`` channel of the `python developers slack community`_.
Want to join? `Get an invite`_ !

.. _open an issue: https://github.com/pyslackers/sirbot-slack/issues
.. _Get an invite: http://pyslackers.com/
.. _python developers slack community: https://pythondev.slack.com/
