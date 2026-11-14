"""Privacy and rules checks for the updated checkpoint adapter."""
import copy
import unittest

from rebel_v2_bridge import RebelV2Policy, private_observation


class RebelV2BridgeTests(unittest.TestCase):
    def state(self, starter=0, turn=0):
        return {"phase": "BIDDING", "round": 1, "version": 0,
                "turn": turn, "starter": starter, "scores": [0, 0],
                "bid": None, "hands": [[1, 2, 3, 4, 5], [6, 6, 6, 6, 6]],
                "events": []}

    def test_hidden_hand_is_redacted_and_does_not_change_action(self):
        first = self.state()
        second = copy.deepcopy(first)
        second["hands"][1] = [1, 1, 1, 1, 1]
        self.assertEqual(private_observation(first), private_observation(second))
        self.assertNotIn("hands", private_observation(first))
        self.assertNotIn("initial_seed", private_observation(first))
        self.assertEqual(RebelV2Policy(42).act(private_observation(first)),
                         RebelV2Policy(42).act(private_observation(second)))

    def test_quantity_only_no_wild_and_second_seat(self):
        policy = RebelV2Policy(7)
        self.assertEqual(policy.agent.codec.get_legal_action_range(
            policy.agent.codec.encode_bid(2, 5)), (12, 61))
        hand_id = policy.agent.hand_space.roll_to_hand_id((5, 5, 5, 5, 0))
        self.assertEqual(policy.agent.hand_space.count_matches(hand_id, 0), 1)
        state = self.state(starter=1, turn=1)
        self.assertEqual(policy.act(private_observation(state))["type"], "bid")

    def test_reseeded_round_is_repeatable(self):
        policy = RebelV2Policy(13)
        observation = private_observation(self.state())
        first = policy.act(observation)
        policy.reset_match(13)
        self.assertEqual(first, policy.act(observation))


if __name__ == "__main__":
    unittest.main()
