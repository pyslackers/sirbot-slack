===================
Quick Start
===================

|build| |coverage| |doc|

A slack bot built for the people and by the people of the `python developers slack community`_.

Want to join? `Get an invite`_ !

.. _Get an invite: http://pythondevelopers.herokuapp.com/
.. _python developers slack community: https://pythondev.slack.com/
.. |build| image:: https://gitlab.com/PythonDevCommunity/sirbot-plugin-slack/badges/master/build.svg
    :alt: Build status
    :scale: 100%
    :target: https://gitlab.com/PythonDevCommunity/sir-bot-a-lot/commits/master
.. |coverage| image:: https://gitlab.com/PythonDevCommunity/sirbot-plugin-slack/badges/master/coverage.svg
    :alt: Coverage status
    :scale: 100%
    :target: https://gitlab.com/PythonDevCommunity/sir-bot-a-lot/commits/master
.. |doc| image:: https://readthedocs.org/projects/sirbot-plugin-slack/badge/?version=latest
    :alt: Documentation status
    :target: http://sir-bot-a-lot.readthedocs.io/en/latest/?badge=latest

Instalation
-----------

**WARNING:** Sirbot-plugin-slack require `sir-bot-a-lot`_.

The sources for sirbot-slack-plugin can be downloaded from the `gitlab repo`_.

.. code-block:: console

    $ git clone git://gitlab.com/PythonDevCommunity/sirbot-plugin-slack

Once you have a copy of the source, you can install it with:

.. code-block:: console

    $ pip install sirbot-plugin-slack/

.. _sir-bot-a-lot: http://sir-bot-a-lot.readthedocs.io/en/latest/
.. _gitlab repo: https://gitlab.com/PythonDevCommunity/sirbot-plugin-slack


Configuration
-------------

The base Sir-bot-a-lot configuration file for sirbot-slack-plugin look like this:

.. code-block:: yaml

    loglevel: 10
    port: 8080

    core:
      loglevel: 10
      plugins:
      - sirbot-plugin-slack

    sirbot_plugin_slack:
      loglevel: 10
      plugins:
      - sirbot_plugin_slack.example
