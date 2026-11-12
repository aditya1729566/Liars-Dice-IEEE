"""Independent one-die checks for the separate v2 external-sampling trainer."""
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from trainer.train_small import best_response
from scripts.quantize_mccfr_v2 import quantize

ROOT = Path(__file__).resolve().parents[1]
TRAINER = ROOT / 'build/mccfr_v2_trainer'


def run(folder, *arguments):
    return subprocess.run([str(TRAINER), *arguments], cwd=folder, text=True,
                          capture_output=True, check=True)


def independent_exploitability(path):
    saved = json.loads(path.read_text())
    converted = {
        key: {str(12 if action == 'C' else (int(action.split('-')[0]) - 1) * 6
                  + int(action.split('-')[1]) - 1): probability
              for action, probability in distribution.items()}
        for key, distribution in saved['policy'].items()
    }
    for distribution in saved['policy'].values():
        assert abs(sum(distribution.values()) - 1) < 1e-9
    return sum(best_response(converted, player) for player in (0, 1))


class MCCFRV2Tests(unittest.TestCase):
    def test_fixed_point_policy_probabilities(self):
        for weights in ([1.0], [0.2, 0.3, 0.5], [1 / 18] * 18):
            units = quantize(weights)
            self.assertEqual(sum(units), 65535)
            self.assertTrue(all(0 <= value <= 65535 for value in units))
            self.assertLess(max(abs(value / 65535 - expected) for value, expected in zip(units, weights)), 1 / 65535)

    def test_algorithm_invariants(self):
        self.assertEqual(json.loads(run(ROOT, '--self-test').stdout), {'self_test': 'passed'})

    def test_toy_convergence_and_checkpoint_resume(self):
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder) / 'experiments/runs'
            common = ('--toy', '--seed', '42')
            run(folder, '--run-id', 'direct', '--iterations', '10000', '--milestones', '1000,10000', *common)
            early = independent_exploitability(base / 'direct/policy_1000.json')
            late = independent_exploitability(base / 'direct/policy_10000.json')
            self.assertLess(late, early)
            self.assertLess(late, 0.02)
            run(folder, '--run-id', 'resumed', '--iterations', '500', *common)
            run(folder, '--run-id', 'resumed', '--iterations', '10000', '--resume', *common)
            self.assertEqual((base / 'direct/policy_10000.json').read_bytes(),
                             (base / 'resumed/policy_10000.json').read_bytes())
            original = (base / 'resumed/policy_10000.json').read_bytes()
            (base / 'resumed/policy_10000.json').unlink()
            run(folder, '--run-id', 'resumed', '--export-only', *common)
            self.assertEqual((base / 'resumed/policy_10000.json').read_bytes(), original)


if __name__ == '__main__':
    unittest.main()
