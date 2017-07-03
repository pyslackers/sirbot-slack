===========
Quick Start
===========

.. note::

    Before the installation of sirbot-slack you need to make sure
    `Sir-bot-a-lot`_ and the `sirbot-plugins`_ are already installed. See
    `Sir-bot-a-lot installation guide`_ for instructions.

.. _Sir-bot-a-lot: http://sir-bot-a-lot.readthedocs.io/en/latest/
.. _sirbot-plugins: https://github.com/pyslackers/sirbot-plugins/
.. _Sir-bot-a-lot installation guide: http://sir-bot-a-lot.readthedocs.io/en/latest/installation.html

Installation
------------

The sources for sirbot-slack can be downloaded from the `github repo`_.

.. code-block:: console

    $ git clone https://github.com/pyslackers/sirbot-slack.git

Once you have a copy of the source, you can install it with:

.. code-block:: console

    $ pip install sirbot-slack/

.. _github repo: https://github.com/pyslackers/sirbot-slack


Configuration
-------------

The default slack part of the configuration file look like this:

.. literalinclude:: ../sirbot/slack/config.yml


Authentication
**************

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

Slack
*****

Sirbot-slack support two type of slack integration:

    1. `Bot users`_
    2. `Slack apps`_

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


