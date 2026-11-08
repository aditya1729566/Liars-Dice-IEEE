import json
import unittest
from pathlib import Path
from train_exhibit import actions, info_key, modal, payoff
from train_exhibit_v2 import actions as actions_v2, info_key as info_key_v2
from train_small import actions as toy_actions, BIDS, CALL, best_response

ROOT = Path(__file__).resolve().parents[1]


class TrainerTests(unittest.TestCase):
    def test_action_abstraction_and_truth(self):
        hand = (2, 2, 2, 4, 6)
        self.assertEqual(modal(hand), (2, 3))
        self.assertEqual(len(actions(hand, ())), 6)
        self.assertEqual(actions(hand, ((4, 5),)), ['C', '5-5', '5-2'])
        self.assertEqual(actions(hand, ((10, 5),)), ['C'])
        self.assertEqual(payoff((hand, (1, 1, 1, 1, 1)), 1, ((3, 2),)), 1.0)

    def test_saved_policy_normalization_and_keys(self):
        saved = json.loads((ROOT / 'policies' / 'fixed5_cfr.json').read_text())
        self.assertEqual(saved['ruleset'], 'fixed5_score5_quantity_only_v1')
        self.assertEqual(saved['iterations'], 100000)
        self.assertGreater(len(saved['policy']), 1000)
        for key, weights in saved['policy'].items():
            self.assertEqual(len(key.split('|')), 7)
            self.assertAlmostEqual(sum(weights.values()), 1.0)
            self.assertTrue(all(value >= 0 for value in weights.values()))

    def test_wider_candidate_actions_and_public_context(self):
        hand = (2, 2, 2, 4, 6)
        self.assertEqual(actions_v2(hand, ()), [f'1-{f}' for f in range(1, 7)] + ['2-2'])
        self.assertEqual(actions_v2(hand, ((3, 5),)), ['C', '4-5', '4-2', '5-5', '5-2'])
        self.assertEqual(actions_v2(hand, ((10, 5),)), ['C'])
        self.assertNotEqual(info_key_v2(0, 1, hand, ((1, 1), (3, 5))), info_key_v2(0, 1, hand, ((2, 1), (3, 5))))
        saved = json.loads((ROOT / 'policies' / 'fixed5_cfr_v2.json').read_text())
        self.assertEqual(saved['iterations'], 100000)
        self.assertGreater(len(saved['policy']), 20000)
        for key, weights in saved['policy'].items():
            self.assertEqual(len(key.split('|')), 9)
            self.assertAlmostEqual(sum(weights.values()), 1.0)

    def test_exact_toy_uses_quantity_only_order_and_information_sets(self):
        self.assertEqual(len(toy_actions(())), 12)
        self.assertEqual(toy_actions((0,)), list(range(6, 12)) + [CALL])
        self.assertEqual(toy_actions((5,)), list(range(6, 12)) + [CALL])
        self.assertEqual(toy_actions((6,)), [CALL])
        self.assertGreaterEqual(best_response({}, 0) + best_response({}, 1), -1e-9)
        always_call={f'1|{die}|{bid}':{str(CALL):1.0} for die in range(1,7) for bid in range(12)}
        self.assertAlmostEqual(best_response(always_call,0),1.0)
        impossible_open={f'0|{die}|':{'6':1.0} for die in range(1,7)}
        self.assertAlmostEqual(best_response(impossible_open,1),17/18)


if __name__ == '__main__':
    unittest.main()
