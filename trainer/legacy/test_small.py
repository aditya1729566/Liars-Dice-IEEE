import json
import unittest
from pathlib import Path
from trainer.legacy.train_small import actions, payoff
ROOT=Path(__file__).resolve().parents[2]
class SolverTests(unittest.TestCase):
    def test_action_order_and_zero_sum(self):
        self.assertEqual(actions(()),list(range(12)))
        self.assertEqual(actions((11,)),[12])
        self.assertEqual(payoff((1,1),1,0),1)
        self.assertEqual(payoff((2,2),1,0),-1)
    def test_frozen_policy_normalizes(self):
        data=json.loads((ROOT/'policies'/'legacy'/'n1_champion.json').read_text())
        self.assertEqual(data['objective'],'one-round N=1')
        for probabilities in data['policy'].values():
            self.assertAlmostEqual(sum(probabilities.values()),1,places=6)
            self.assertTrue(all(0<=v<=1 for v in probabilities.values()))
if __name__=='__main__':unittest.main()
