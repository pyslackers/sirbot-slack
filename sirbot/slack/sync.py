def add_to_slack(slack):

    slack.add_event('channel_archive', channel_archive)
    slack.add_event('channel_created', channel_created)
    slack.add_event('channel_deleted', channel_deleted)
    slack.add_event('channel_joined', channel_joined)
    slack.add_event('channel_left', channel_left)
    slack.add_event('channel_rename', channel_rename)
    slack.add_event('channel_unarchive', channel_unarchive)

    slack.add_event('group_archive', group_archive)
    slack.add_event('group_joined', group_joined)
    slack.add_event('group_left', group_left)
    slack.add_event('group_rename', group_rename)
    slack.add_event('group_unarchive', group_unarchive)

    slack.add_event('user_typing', user_typing)
    slack.add_event('team_join', team_join)


async def channel_archive(event, slack, _):
    """
    Use the channel archive event to delete the channel
    from the ChannelManager
    """
    await slack.channels.get(event['channel'], fetch=True)


async def channel_created(event, slack, _):
    """
    Use the channel created event to add the channel
    to the ChannelManager
    """
    await slack.channels.get(event['channel']['id'], fetch=True)


async def channel_deleted(event, slack, _):
    """
    Use the channel delete event to delete the channel
    from the ChannelManager
    """
    await slack.channels.get(event['channel'], fetch=True)


async def channel_joined(event, slack, _):
    """
    Use the channel joined event to update the channel status
    """
    await slack.channels.get(event['channel']['id'], fetch=True)


async def channel_left(event, slack, _):
    """
    Use the channel left event to update the channel status
    """
    await slack.channels.get(event['channel'], fetch=True)


async def channel_rename(event, slack, _):
    """
    User the channel rename event to update the name
    of the channel
    """
    await slack.channels.get(event['channel']['id'], fetch=True)


async def channel_unarchive(event, slack, _):
    """
    Use the channel unarchive event to delete the channel
    from the ChannelManager
    """
    await slack.channels.get(event['channel'], fetch=True)


async def group_archive(event, slack, _):
    """
    Use the channel archive event to delete the channel
    from the ChannelManager
    """
    await slack.groups.get(event['channel'], fetch=True)


async def group_joined(event, slack, _):
    """
    Use the channel joined event to update the channel status
    """
    await slack.groups.get(event['channel']['id'], fetch=True)


async def group_left(event, slack, _):
    """
    Use the channel left event to update the channel status
    """
    await slack.groups.get(event['channel'], fetch=True)


async def group_rename(event, slack, _):
    """
    User the channel rename event to update the name
    of the channel
    """
    await slack.groups.get(event['channel']['id'], fetch=True)


async def group_unarchive(event, slack, _):
    """
    Use the channel unarchive event to delete the channel
    from the ChannelManager
    """
    await slack.groups.get(event['channel'], fetch=True)


async def user_typing(event, slack, _):
    """
    Use the user typing event to make sure the user is in cache
    """
    await slack.users.get(event['user'])


async def team_join(event, slack, _):
    """
    Use the team join event to add an user to the user store
    """
    await slack.users.get(event['user']['id'])
