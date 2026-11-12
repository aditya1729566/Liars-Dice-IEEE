"""Independent exact one-die checks for the C++ external-sampling trainer."""
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from trainer.train_small import best_response

ROOT = Path(__file__).resolve().parents[1]
TRAINER = ROOT / 'build' / 'mccfr_trainer'


def run(cwd, *args):
    return subprocess.run([str(TRAINER), *args], cwd=cwd, text=True,
                          capture_output=True, check=True)


def exact_policy(path):
    saved = json.loads(path.read_text())
    converted = {
        key: {str(12 if action == 'C' else (int(action.split('-')[0]) - 1) * 6
                  + int(action.split('-')[1]) - 1): weight
              for action, weight in distribution.items()}
        for key, distribution in saved['policy'].items()
    }
    return saved, converted


class MCCFRTests(unittest.TestCase):
    def test_algorithm_invariants(self):
        self.assertEqual(json.loads(run(ROOT, '--self-test').stdout), {'self_test': 'passed'})

    def test_toy_convergence_and_average(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            base = ['--toy', '--seed', '42', '--checkpoint-every', '1000']
            run(root, '--run-id', 'toy', '--iterations', '10000', *base)
            one, policy1 = exact_policy(root / 'experiments/runs/toy/policy_1000.json')
            ten, policy10 = exact_policy(root / 'experiments/runs/toy/policy_10000.json')
            for saved in (one, ten):
                self.assertEqual(saved['policy_id'], 'mccfr_external_toy')
                for distribution in saved['policy'].values():
                    self.assertAlmostEqual(sum(distribution.values()), 1.0, places=9)
                    self.assertTrue(all(0 <= x <= 1 for x in distribution.values()))
            exploit1 = sum(best_response(policy1, p) for p in (0, 1))
            exploit10 = sum(best_response(policy10, p) for p in (0, 1))
            self.assertLess(exploit10, exploit1)
            self.assertLess(exploit10, 0.03)

    def test_checkpoint_resume_reproducibility(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            args = ['--toy', '--seed', '1729', '--checkpoint-every', '500']
            run(root, '--run-id', 'direct', '--iterations', '1000', *args)
            run(root, '--run-id', 'resumed', '--iterations', '500', *args)
            run(root, '--run-id', 'resumed', '--iterations', '1000', *args, '--resume')
            base = root / 'experiments/runs'
            self.assertEqual((base / 'direct/policy_1000.json').read_bytes(),
                             (base / 'resumed/policy_1000.json').read_bytes())
            self.assertEqual((base / 'direct/checkpoint.json').read_bytes(),
                             (base / 'resumed/checkpoint.json').read_bytes())
            original = (base / 'direct/policy_1000.json').read_bytes()
            (base / 'direct/policy_1000.json').unlink()
            run(root, '--run-id', 'direct', '--seed', '1729', '--toy', '--export-only')
            self.assertEqual((base / 'direct/policy_1000.json').read_bytes(), original)


if __name__ == '__main__':
    unittest.main()
