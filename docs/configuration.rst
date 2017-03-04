.. _configuration:

=============
Configuration
=============

Sir-bot-a-lot configuration is a Yaml file containing the core and all the plugins
configuration.

The environment variable and command line arguments take precedence over the
configuration file.

For more information see `Sir-bot-a-lot configuration documentation`_.

.. _Sir-bot-a-lot configuration documentation: http://sir-bot-a-lot.readthedocs.io/en/latest/configuration.html


Environment variable
--------------------

* :code:`SIRBOT_SLACK_TOKEN`: Token to access the slack API


Configuration file
------------------

example
^^^^^^^

A basic configuration to activate sirbot-plugin-slack will look like this:

.. code-block:: yaml

    loglevel: 10
    port: 8080

    core:
      loglevel: 20
      plugins:
        - sirbot_plugin_slack
    sirbot_plugin_slack:
      loglevel: 10
      plugins:
      - sirbot_plugin_slack.example
