=====================
Usage & Configuration
=====================

For usage and configuration of Sir-bot-a-lot core take a look at `Usage & Configuration`_

.. _Usage & Configuration: http://sir-bot-a-lot.readthedocs.io/en/latest/usage.html

By itself Sir-bot-a-lot will not react to any events or messages happening in
the slack team he joined. It will only try to keep the list of channel and user
up to date.

To enable Sir-bot-a-lot to react you need to add others plugins (An example
plugins is available: :code:`sirbot_plugin_slack.example`)

For more information take a look at :ref:`how to write plugins<writing_plugins>`.

Environment variables
---------------------

* :code:`SIRBOT_SLACK_TOKEN`: Token to access the slack API (Mandatory)

Configuration file
------------------

A basic configuration for Sirbot_plugin_slack will look like this:

.. code-block:: yaml

    core:
        plugins:
            - sirbot_plugin_slack

    sirbot_plugin_slack:
        plugins:
            - sirbot_plugin_slack.example
