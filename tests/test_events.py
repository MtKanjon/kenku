from io import StringIO
from multiprocessing import dummy
from textwrap import dedent
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


def test_can_record_point(event_manager: EventManager, make_channel, make_message):
    dummy_channel = make_channel()
    dummy_message = make_message()
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


def test_season_scoring(event_manager: EventManager, make_channel):
    dummy_channel = make_channel()
    event_manager.configure_channel(dummy_channel)

    # TODO:
    # check scoring multiple channels
    # check point multipliers
    # check that removing a channel removes scores


async def test_adjustments(
    event_manager: EventManager, make_channel, dummy_context, make_message, make_user
):
    dummy_channel = make_channel()
    event_manager.configure_channel(dummy_channel, 2)

    csv = StringIO(
        dedent(
            """user_id,user_name,adjustment,note
            111,kanjon,50,im the best
            111,kanjon,20,20 more as a treat
            222,spine,-1,teehee
            """
        )
    )
    await event_manager.replace_adjustments(dummy_context, dummy_channel.id, csv)

    # adjusted scores are not affected by multiplier
    scores = event_manager.get_event_leaderboard(dummy_channel.id)
    expected = {
        111: 70,
        222: -1,
    }
    assert expected == scores

    # but they do add in with multiplied scores from reactions
    msg = make_message(7777, make_user(111), dummy_channel)
    event_manager.set_points(msg, 3)
    scores = event_manager.get_event_leaderboard(dummy_channel.id)
    expected = {
        111: 70 + 2 * 3,
        222: -1,
    }
    assert expected == scores

    # adjustments can be removed
    csv = StringIO("user_id,user_name,adjustment,note")
    await event_manager.replace_adjustments(dummy_context, dummy_channel.id, csv)
    scores = event_manager.get_event_leaderboard(dummy_channel.id)
    expected = {
        111: 2 * 3,
    }
    assert expected == scores
