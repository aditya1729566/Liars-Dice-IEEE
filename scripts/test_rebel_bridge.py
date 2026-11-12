"""Integration checks for the pinned, local ReBeL transfer adapter."""
import copy
import unittest

from rebel_bridge import RebelPolicy, private_observation


class RebelBridgeTests(unittest.TestCase):
    def state(self, turn=0, starter=0):
        return {"phase": "BIDDING", "round": 1, "turn": turn, "starter": starter,
                "bid": None, "hands": [[1, 2, 3, 4, 5], [6, 6, 6, 6, 6]],
                "events": [], "scores": [0, 0]}

    def test_hidden_opponent_hand_is_absent_and_cannot_change_action(self):
        original = self.state()
        changed = copy.deepcopy(original)
        changed["hands"][1] = [1, 1, 1, 1, 1]
        first = private_observation(original)
        second = private_observation(changed)
        self.assertEqual(first, second)
        self.assertIsNone(first["hands"][1])
        self.assertEqual(RebelPolicy(7).act(first), RebelPolicy(7).act(second))

    def test_second_seat_and_quantity_only_legality(self):
        state = self.state(turn=1, starter=0)
        state["events"] = [{"type": "bid", "round": 1, "q": 2, "f": 6, "player": "HUMAN"}]
        state["bid"] = {"q": 2, "f": 6}
        action = RebelPolicy(42).act(private_observation(state))
        self.assertTrue(action["type"] == "call" or action["q"] > 2)

    def test_reseeded_match_replays_the_same_opening(self):
        policy = RebelPolicy(17)
        observation = private_observation(self.state())
        first = policy.act(observation)
        policy.reset_match(17)
        self.assertEqual(first, policy.act(observation))


if __name__ == "__main__":
    unittest.main()
