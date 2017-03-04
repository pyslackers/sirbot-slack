=====
Usage
=====

Sir-bot-a-lot
-------------

Command Line
^^^^^^^^^^^^

To start Sir-bot-a-lot you can use:

.. code-block:: console

    $ sirbot

or:

.. code-block:: console

    $ python run.py

Import
^^^^^^

To use Sir-bot-a-lot in a project:

.. code-block:: python

    from sirbot import SirBot
    bot = SirBot(config=config)
    bot.run(port=port)


Sirbot-plugin-slack
-------------------

Once Sir-bot-a-lot is started and connected to slack, thanks to
sirbot-plugin-slack, it will only keep the slack channel list and the slack
user list up to date (thanks to the mandatory plugin
:code:`sirbot_plugin_slack.user` and :code:`sirbot_plugin_slack.channel`).
If you want it to react to incoming messages or events you must add some plugins
to sirbot-plugin-slack. For testing purpose you can add the
:code:`sirbot_plugin_slack.example` plugins that defined some examples events
and messages callbacks.

For more information take a look at :ref:`how to write plugins<writing_plugins>`.
