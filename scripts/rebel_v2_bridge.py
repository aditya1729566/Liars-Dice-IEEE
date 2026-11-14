"""Adapter for the upstream BLUFF.EXE-specific ReBeL checkpoint.

The upstream source runs in a separate Python process so its ``game`` and
``agents`` packages cannot collide with the preserved transfer-v1 source.
Only the acting hand and public information enter this adapter.
"""
from __future__ import annotations

import hashlib
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = Path(os.environ.get("BLUFF_REBEL_SOURCE_V2", ROOT / ".cache" / "rebel-source-v2"))
CHECKPOINT = SOURCE / "checkpoints" / "bluff_exe_v1" / "rebel_bluff_epoch_5.pt"
SOURCE_COMMIT = "05607c7a208189ac6b0149337f45d46ad3828894"
CHECKPOINT_SHA256 = "6c629db416e337bbce06e07375238b62fa3e414b8d36ae01b90635175fdbbc77"
AGENT_ID = "rebel_bluff_v2"


def available() -> bool:
    try:
        import torch  # noqa: F401
        return (CHECKPOINT.is_file() and
                hashlib.sha256(CHECKPOINT.read_bytes()).hexdigest() == CHECKPOINT_SHA256 and
                (SOURCE / "game" / "bluff_engine.py").is_file())
    except (ImportError, OSError):
        return False


def private_observation(state: dict) -> dict:
    player = state["turn"]
    return {"phase": state["phase"], "round": state["round"],
            "version": state.get("version"), "turn": player,
            "starter": state["starter"], "scores": state["scores"],
            "bid": state["bid"],
            "hand": state["hands"][player],
            "events": [{"type": "bid", "round": e["round"], "q": e["q"], "f": e["f"]}
                       for e in state["events"]
                       if e.get("round") == state["round"] and e["type"] == "bid"]}


class RebelV2Policy:
    def __init__(self, seed: int, search_iters: int = 32, search_depth: int = 1):
        if not available():
            raise RuntimeError("updated ReBeL source, checkpoint, or PyTorch unavailable; run make setup-rebel-v2")
        if str(SOURCE) not in sys.path:
            sys.path.insert(0, str(SOURCE))
        import numpy as np
        import torch
        from agents.rebel_agent import RebelAgent
        from game.config import GameConfig
        from models.value_net import ValueNet

        torch.set_num_threads(1)
        payload = torch.load(CHECKPOINT, map_location="cpu", weights_only=True)
        config = payload.get("config_dict", {})
        expected = {"ruleset": "BLUFF_EXE_V1", "bidding_rule": "quantity_only",
                    "wild_face_mode": "none", "points_to_win": 5,
                    "num_players": 2, "num_dice_per_player": 5, "num_faces": 6,
                    "hand_representation": "multiset", "algorithm": "linear_fp"}
        if any(config.get(key) != value for key, value in expected.items()):
            raise RuntimeError("updated ReBeL checkpoint has incompatible rules or architecture")
        if payload.get("input_size") != 567 or payload.get("output_size") != 252 or payload.get("epoch") != 5:
            raise RuntimeError("unexpected updated ReBeL checkpoint dimensions or epoch")
        net = ValueNet(payload["input_size"], payload["output_size"],
                       payload["n_hidden"], payload["n_layers"])
        net.load_state_dict(payload["model_state_dict"])
        net.eval()
        self.agent = RebelAgent(GameConfig.bluff_exe(), value_net=net,
                                device=torch.device("cpu"), search_depth=search_depth,
                                search_iters=search_iters, seed=seed)
        self.round_number = None
        self.search_iters = search_iters
        self.search_depth = search_depth
        self.checkpoint_sha256 = CHECKPOINT_SHA256

    def reset_match(self, seed: int):
        import numpy as np
        self.agent.rng = np.random.default_rng(seed)
        self.round_number = None
        self.agent.reset(opening_player=0)

    def act(self, observation: dict) -> dict:
        if observation["phase"] != "BIDDING":
            raise ValueError("ReBeL requested outside bidding")
        round_number = observation["round"]
        starter = observation["starter"]
        if self.round_number != round_number:
            self.agent.reset(opening_player=starter)
            self.agent._current_round_num = round_number
            self.round_number = round_number
        from game.state import BluffPlayerObservation, PublicState

        player = observation["turn"]
        own_dice = observation["hand"]
        if len(own_dice) != 5 or any(not isinstance(d, int) or not 1 <= d <= 6 for d in own_dice):
            raise ValueError("invalid private hand")
        history = tuple(self.agent.codec.encode_bid(e["q"], e["f"] - 1)
                        for e in observation["events"])
        if player != (starter + len(history)) % 2:
            raise ValueError("public history does not match the active seat")
        own_hand_id = self.agent.hand_space.roll_to_hand_id(tuple(d - 1 for d in own_dice))
        player_observation = BluffPlayerObservation(
            player_id=player, own_hand_id=own_hand_id,
            own_dice_counts=self.agent.hand_space.get_counts(own_hand_id),
            public_state=PublicState(active_player=player,
                                     last_action_id=history[-1] if history else -1,
                                     history=history),
            scores=tuple(observation["scores"]), round_number=round_number,
            opener=starter)
        self.agent._sync_pbs(player_observation)
        search = self.agent.solver.solve(root_pbs=self.agent._current_pbs,
                                         max_depth=self.search_depth,
                                         num_iters=self.search_iters,
                                         linear_update=True)
        action_id = search.sample_action(own_hand_id, rng=self.agent.rng)
        import numpy as np
        raw = search.get_action_strategy(own_hand_id)
        weights = np.asarray([max(0.0, float(raw[aid])) for aid in search.legal_actions])
        weights = weights / weights.sum() if weights.sum() > 1e-12 else np.full(len(weights), 1 / len(weights))
        ranked = sorted(zip(search.legal_actions, weights), key=lambda item: -item[1])[:3]
        self.last_metadata = {
            "policy_probability": float(weights[search.legal_actions.index(action_id)]),
            "policy_options": [{"action": "C" if aid == self.agent.codec.challenge_id else
                                f"{self.agent.codec.decode(aid).quantity}-{self.agent.codec.decode(aid).face + 1}",
                                "weight": float(weight)} for aid, weight in ranked],
            "search_elapsed_ms": search.elapsed_ms,
            "search_tree_size": search.tree_size,
        }
        self.agent._current_pbs = self.agent.updater.update(self.agent._current_pbs, action_id, search.root_strategy)
        self.agent._last_history_len += 1
        action = self.agent.codec.decode(action_id)
        result = {"type": "call"} if action.is_challenge else {"type": "bid", "q": action.quantity, "f": action.face + 1}
        if result["type"] == "call" and not observation["bid"]:
            raise ValueError("ReBeL challenged an opening state")
        if result["type"] == "bid" and observation["bid"] and result["q"] <= observation["bid"]["q"]:
            raise ValueError("ReBeL made a non-increasing bid")
        return result
