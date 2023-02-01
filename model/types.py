from dataclasses import dataclass
from enum import IntEnum

from discord import Thread
from discord.abc import GuildChannel, PrivateChannel

Channel = GuildChannel | Thread | PrivateChannel | None


@dataclass
class SquadPlayer:
    name: str
    confirmed: bool


@dataclass
class Squad:
    player_1: SquadPlayer
    player_2: SquadPlayer

    def has_player(self, name: str) -> bool:
        return self.player_1.name == name or self.player_2.name == name

    def get_player(self, name: str) -> SquadPlayer | None:
        if self.player_1.name == name:
            return self.player_1

        if self.player_2.name == name:
            return self.player_2

        return None


class SquadStatus(IntEnum):
    CALLER_IN_OTHER_SQUAD = 1,  # if the caller is already in a different unconfirmed squad
    NEITHER_UNCONFIRMED = 2,  # if neither are unconfirmed
    WAITING_ON_PARTNER = 3,  # if the caller is waiting on their partner
    CONFIRMING = 4  # the caller is confirming, finishing the confirmation process and adding to queue
