.. _plugins:

=======
Plugins
=======

Plugins must be used to register callbacks on incoming messages or events.

Available plugins
-----------------

The `sirbot-plugin-pythondev`_ as some plugins available.

.. _sirbot-plugin-pythondev: https://gitlab.com/PythonDevCommunity/sirbot-plugin-pythondev

.. _writing_plugins:

Writing plugins
---------------

Hooks
^^^^^

Two hooks are available. The first one to register function on slack messages and the second
one on slack events

.. literalinclude:: ../sirbot/slack/hookspecs.py

Messages
^^^^^^^^

This hook should return a list of dictionary with the following keys:

* match: Regular expression used to identify which message to match
* func: Function that will be called on matched messages
* on_mention: Specify if the message should match only when the bot is mentioned
* flags: Regular expression flags

.. code-block:: python

    @hookimpl
    def register_slack_messages():
        commands = [
                {
            'match': 'test message',
            'func': test_message,
            'on_mention': True,
            'flags': re.IGNORECASE
            }
        ]

        return commands

Events
^^^^^^

This hook should return a list of dictionary with the following keys:

* name: Name of the event to match (see `events list`_)
* func: Function that will be called on matched event

.. code-block:: python

    @hookimpl
    def register_slack_events():

        events = [
            {
                'func': hello_world,
                'name': 'user_typing'
            }
        ]

        return events

.. _events list: https://api.slack.com/events

Example
-------

Full examples are available in the :code:`example.py` file

.. literalinclude:: ../sirbot/slack/example.py