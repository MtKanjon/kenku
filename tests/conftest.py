from dataclasses import dataclass
import datetime
import pytest

import discord


@pytest.fixture
def dummy_guild():
    @dataclass
    class Guild:
        id: int

    return Guild(id=9876)


@pytest.fixture
def make_channel(dummy_guild):
    @dataclass
    class Channel:
        id: int
        name: str
        guild: discord.Guild

    def _make_channel(name="dummy-channel"):
        return Channel(id=222, name=name, guild=dummy_guild)

    return _make_channel


@pytest.fixture
def make_user(dummy_guild):
    @dataclass
    class User:
        id: int
        name: str
        discriminator: int
        guild: discord.Guild

    def _make_user(id=4321, name="dummy-user"):
        return User(id=id, name=name, discriminator=1111, guild=dummy_guild)

    return _make_user


@pytest.fixture
def make_message(make_channel, make_user, dummy_guild):
    @dataclass
    class Message:
        id: int
        author: discord.User
        channel: discord.TextChannel
        guild: discord.Guild
        created_at: datetime.datetime

    def _make_message(id=222, author=make_user(), channel=make_channel()):
        return Message(
            id=id,
            author=author,
            channel=channel,
            guild=dummy_guild,
            created_at=datetime.datetime.now(),
        )

    return _make_message


@pytest.fixture
def dummy_context(dummy_guild):
    @dataclass
    class Context:
        guild: discord.Guild

    return Context(guild=dummy_guild)
