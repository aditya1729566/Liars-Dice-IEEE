"""Exact toy-game verification of quantity-only bidding with one die per player.

This is not a playable game mode or a five-dice policy. Full histories and all
36 chance deals are enumerated; a separate information-respecting best response
checks the average strategy.
"""
import argparse
import hashlib
import json
import pickle
import time
from collections import defaultdict
from pathlib import Path

BIDS = [(q, f) for q in (1, 2) for f in range(1, 7)]
CALL = 12
ROOT = Path(__file__).resolve().parents[1]


def actions(history):
    if not history:return list(range(12))
    return list(range(6,12)) + [CALL] if BIDS[history[-1]][0]==1 else [CALL]


def key(player, die, history):
    return f"{player}|{die}|{','.join(map(str, history))}"


def payoff(dice, caller, bid):
    q, f = BIDS[bid]
    true = (dice[0] == f) + (dice[1] == f) >= q
    winner = 1 - caller if true else caller
    return 1.0 if winner == 0 else -1.0


def current(regrets, k, acts):
    positive = [max(0.0, regrets[k].get(a, 0.0)) for a in acts]
    total = sum(positive)
    return [x / total for x in positive] if total else [1 / len(acts)] * len(acts)


def cfr(dice, history, turn, reach, regrets, sums, delta):
    acts = actions(history)
    k = key(turn, dice[turn], history)
    strategy = current(regrets, k, acts)
    values = []
    for a in acts:
        if a == CALL:
            value = payoff(dice, turn, history[-1])
        else:
            new_reach = list(reach)
            new_reach[turn] *= strategy[acts.index(a)]
            value = cfr(dice, history + (a,), 1 - turn, new_reach, regrets, sums, delta)
        values.append(value)
    node = sum(p * v for p, v in zip(strategy, values))
    for a, p, v in zip(acts, strategy, values):
        delta[k][a] += (v - node) * (1 if turn == 0 else -1) * reach[1 - turn] / 36
        sums[k][a] = sums[k].get(a, 0.0) + p * reach[turn] / 36
    return node


def average(sums):
    policy = {}
    for k, weights in sums.items():
        total = sum(weights.values())
        if total:
            policy[k] = {str(a): v / total for a, v in weights.items()}
    return policy


def best_response(policy, br_player):
    # Opponent's six possible dice are kept as a belief vector. One action is
    # selected for the whole information set, never per hidden opponent die.
    other = 1 - br_player
    def solve(own, history, turn, belief):
        acts = actions(history)
        if turn == br_player:
            vals = []
            for a in acts:
                if a == CALL:
                    vals.append(sum(w * payoff((own, d) if br_player == 0 else (d, own), turn, history[-1]) * (1 if br_player == 0 else -1) for d, w in enumerate(belief, 1)))
                else:
                    vals.append(solve(own, history + (a,), other, belief))
            return max(vals)
        total = 0.0
        for a in acts:
            next_belief = []
            for d, w in enumerate(belief, 1):
                probs = policy.get(key(other, d, history), {})
                next_belief.append(w * (probs.get(str(a), 0.0) if probs else 1 / len(acts)))
            if a == CALL:
                total += sum(w * payoff((own, d) if br_player == 0 else (d, own), turn, history[-1]) * (1 if br_player == 0 else -1) for d, w in enumerate(next_belief, 1))
            else:
                total += solve(own, history + (a,), br_player, next_belief)
        return total
    return sum(solve(own, (), 0, [1 / 6] * 6) for own in range(1, 7)) / 6


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--iterations", type=int, default=100)
    parser.add_argument("--run-id", default="small_n1")
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    if not 1 <= args.iterations <= 5000:
        raise SystemExit("iterations must be 1..5000")
    out = ROOT / "experiments" / "runs" / args.run_id
    checkpoint=out/"checkpoint.pkl"
    if args.resume:
        if not checkpoint.exists():raise SystemExit("checkpoint not found")
        saved=pickle.loads(checkpoint.read_bytes())
        start_iteration,regrets,sums=saved["iteration"],saved["regrets"],saved["sums"]
        if start_iteration>=args.iterations:raise SystemExit("target iteration must exceed checkpoint iteration")
    else:
        out.mkdir(parents=True, exist_ok=False)
        start_iteration=0;regrets,sums=defaultdict(dict),defaultdict(dict)
    (out / "manifest.json").write_text(json.dumps({"ruleset": "quantity_only_n1_toy", "objective": "one-round N=1 +1/-1 challenge utility", "algorithm": "exact full-tree tabular CFR", "iterations_planned": args.iterations, "iterations_from_checkpoint":start_iteration,"status": "started", "command": f"python3.12 trainer/train_small.py --iterations {args.iterations} --run-id {args.run_id}"}, indent=2))
    started = time.time()
    try:
        for iteration in range(start_iteration,args.iterations):
            delta = defaultdict(lambda: defaultdict(float))
            for a in range(1, 7):
                for b in range(1, 7):
                    cfr((a, b), (), 0, (1.0, 1.0), regrets, sums, delta)
            for k, vals in delta.items():
                row = regrets[k]
                for action, value in vals.items():
                    row[action] = row.get(action, 0.0) + value
            if (iteration + 1) % 10 == 0 or iteration + 1 == args.iterations:
                pending=out/"checkpoint.pending"
                pending.write_bytes(pickle.dumps({"iteration":iteration+1,"regrets":regrets,"sums":sums},protocol=5))
                pending.replace(checkpoint)
                print(json.dumps({"iteration": iteration + 1, "infosets": len(regrets), "elapsed_seconds": round(time.time() - started, 2)}), flush=True)
        policy = average(sums)
        policy_path = out / "policy.json"
        policy_path.write_text(json.dumps({"ruleset": "quantity_only_n1_toy", "objective": "one-round N=1", "iterations": args.iterations, "policy": policy}, separators=(",", ":")))
        br0,br1=best_response(policy,0),best_response(policy,1)
        result = {"best_response_p0": br0, "best_response_p1": br1, "nashconv": br0+br1, "nashconv_definition": "sum of each player's exact information-set-respecting best-response payoff against the opponent average strategy; one-round one-die toy only", "infosets": len(policy), "elapsed_seconds": time.time() - started, "policy_sha256": hashlib.sha256(policy_path.read_bytes()).hexdigest()}
        (out / "summary.json").write_text(json.dumps(result, indent=2))
        (out / "manifest.json").write_text(json.dumps({"ruleset": "quantity_only_n1_toy", "objective": "one-round N=1 +1/-1 challenge utility", "algorithm": "exact full-tree tabular CFR", "iterations_completed": args.iterations, "status": "completed", "result": result}, indent=2))
        print(json.dumps(result), flush=True)
    except BaseException as exc:
        (out / "failure.json").write_text(json.dumps({"error": repr(exc), "elapsed_seconds": time.time() - started}))
        raise


if __name__ == "__main__":
    main()
