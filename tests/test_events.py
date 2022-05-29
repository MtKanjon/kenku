from typing import cast
import pytest

from redbot.core import commands

from cogs.crow.events.manager import EventManager


@pytest.fixture
def event_manager():
    return EventManager(cast(commands.Cog, None), storage_path=":memory:")


def test_can_configure_channel(
    event_manager: EventManager, make_channel, dummy_context
):
    dummy_channel = make_channel()

    # add a channel
    event_manager.configure_channel(dummy_channel)
    _season, channels = event_manager.get_season_channels(dummy_context)
    assert 1 == len(channels)
    assert dummy_channel.id == channels[0]["channel_id"]

    # and remove it
    event_manager.configure_channel(dummy_channel, 0)
    _season, channels = event_manager.get_season_channels(dummy_context)
    assert 0 == len(channels)


def test_can_record_point(
    event_manager: EventManager, make_channel, dummy_message, dummy_context
):
    dummy_channel = make_channel()
    event_manager.configure_channel(dummy_channel)

    # add a point
    event_manager.set_points(dummy_message, 3)
    _season, scores = event_manager.user_info(dummy_message.author)
    assert 1 == len(scores)
    assert dummy_channel.id == scores[0]["channel_id"]
    assert 3 == scores[0]["score"]

    # and remove it
    event_manager.set_points(dummy_message, 0)
    _season, scores = event_manager.user_info(dummy_message.author)
    assert 1 == len(scores)
    assert dummy_channel.id == scores[0]["channel_id"]
    assert 0 == scores[0]["score"]


def test_season_scoring(
    event_manager: EventManager, make_channel, dummy_message, dummy_context
):
    dummy_channel = make_channel()
    event_manager.configure_channel(dummy_channel)

    # TODO:
    # check scoring multiple channels
    # check point multipliers
    # check that removing a channel removes scores
