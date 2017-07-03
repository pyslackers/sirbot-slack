=============
Configuration
=============

.. _authentification:

Authentication
--------------

Slack connection information are provided as environment variables:

    * ``SIRBOT_SLACK_BOT_TOKEN``
        * Starting with ``xoxb``
        * Needed to connect to the RTM api
    * ``SIRBOT_SLACK_TOKEN``
        * Starting with ``xoxp``
        * Only for slack apps
    * ``SIRBOT_SLACK_VERIFICATION_TOKEN``
        * Webhook verification token
        * Only for slack apps


Configuration file
------------------

The default slack part of the configuration file look like this:

.. literalinclude:: ../sirbot/slack/config.yml

Plugins requirements
--------------------

Sirbot-slack needs the `sirbot-sqlite`_ plugin to work. it must be configured to
start before sirbot-slack with the `priority`_ key of the configuration file.

.. _sirbot-sqlite: https://github.com/pyslackers/sirbot-plugins
.. _priority: http://sir-bot-a-lot.readthedocs.io/en/latest/configuration.html#starting-priority

Slack apps & Bot users
----------------------

Sirbot-slack support two type of slack integration:

    1. `Slack apps`_
    2. `Bot users`_

Useful links to get started:

    * `Create a team`_
    * `Building slack apps`_
    * `Ngrok`_ for local testing
    * `Using ngrok to develop locally for Slack`_


.. _Bot users: https://api.slack.com/bot-users
.. _Slack apps: https://api.slack.com/slack-apps

.. _Create a team: https://slack.com/create#email
.. _Building slack apps: https://api.slack.com/slack-apps
.. _Ngrok: https://ngrok.com/
.. _Using ngrok to develop locally for Slack: https://api.slack.com/tutorials/tunneling-with-ngrok
