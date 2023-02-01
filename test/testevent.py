from model.event import Event
from model.types import Channel, SquadPlayer, Squad


class TestEvent(Event):
    def __init__(self, channel: Channel):
        super().__init__(channel)
        players = ['test1', 'test2', 'test3', 'test4', 'test5', 'test6',
                   'test7', 'test8', 'test9', 'test10', 'test11']
        self.queue_flat = [player for player in players]
        self.queue = [player for player in players]
        # marcille = SquadPlayer('marcille', True)
        # aa = SquadPlayer('AA', False)
        # self.unconfirmed_squads = [Squad(marcille, aa)]
        self.queue_num = len(players)
