import copy
import unittest

from server.replay import build_replay, truth_prior


class ReplayTests(unittest.TestCase):
    def test_complete_event_order_and_human_interpretation_privacy(self):
        state = {
            'status': 'COMPLETED', 'round': 1, 'ai_decisions': [],
            'events': [
                {'type': 'round_start', 'round': 1, 'starter': 'HUMAN', 'scores': [4, 0]},
                {'type': 'bid', 'round': 1, 'sequence': 1, 'player': 'HUMAN', 'q': 2, 'f': 3},
                {'type': 'reveal', 'round': 1, 'caller': 'AI', 'bidder': 'HUMAN',
                 'bid': {'q': 2, 'f': 3}, 'actual': 3, 'true': True, 'winner': 'HUMAN',
                 'hands': [[3, 3, 1, 2, 4], [3, 1, 1, 5, 6]], 'scores': [5, 0]},
                {'type': 'match_end', 'winner': 'HUMAN', 'scores': [5, 0]},
            ],
        }
        frames = build_replay(state)
        self.assertEqual([frame['kind'] for frame in frames],
                         ['round_start', 'bid', 'call', 'reveal', 'match_end'])
        self.assertEqual(frames[1]['hands'], state['events'][2]['hands'])
        self.assertEqual(frames[1]['human_support'], 2)
        self.assertEqual(frames[1]['ai_support'], 1)
        self.assertEqual(frames[1]['actual_count'], 3)
        self.assertAlmostEqual(frames[1]['ai_truth_prior'], truth_prior(2, 3, [3, 1, 1, 5, 6]))
        self.assertIn('I cannot know your intent', frames[1]['ai_read'])
        changed = copy.deepcopy(state)
        changed['events'][2]['hands'][0] = [1, 1, 1, 1, 1]
        alternate = build_replay(changed)
        self.assertEqual(frames[1]['ai_read'], alternate[1]['ai_read'])
        self.assertNotEqual(frames[1]['actual_count'], alternate[1]['actual_count'])

    def test_active_match_cannot_replay(self):
        with self.assertRaises(ValueError):
            build_replay({'status': 'ACTIVE'})


if __name__ == '__main__':
    unittest.main()
