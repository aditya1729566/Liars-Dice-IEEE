"""Pinned upstream ReBeL checkpoint adapter for the local quantity-only game.

The upstream source and weights are fetched separately; they are not vendored
because the source repository does not provide a license.  This adapter changes
only the legal-action ordering and wild-face configuration at inference time.
"""
from __future__ import annotations

import hashlib
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = Path(os.environ.get("BLUFF_REBEL_SOURCE", ROOT / ".cache" / "rebel-source"))
CHECKPOINT = SOURCE / "checkpoints" / "rebel_5x6f_epoch_6.pt"
SOURCE_COMMIT = "1d915cc2dcecf9670aaec652ab78bf528241ce21"
AGENT_ID = "rebel_transfer_v1"


def private_observation(state: dict) -> dict:
    """Give the bridge only the acting hand and current-round public moves."""
    player = state["turn"]
    return {"phase": state["phase"], "round": state["round"], "version": state.get("version"),
            "turn": player, "starter": state["starter"], "bid": state["bid"],
            "hands": [state["hands"][0] if player == 0 else None,
                      state["hands"][1] if player == 1 else None],
            "events": [{"type": e["type"], "round": e["round"],
                        **({"q": e["q"], "f": e["f"]} if e["type"] == "bid" else {})}
                       for e in state["events"] if e.get("round") == state["round"] and e["type"] == "bid"]}


def available() -> bool:
    try:
        import torch  # noqa: F401
        return CHECKPOINT.is_file() and (SOURCE / "agents" / "rebel_agent.py").is_file()
    except ImportError:
        return False


class RebelPolicy:
    """One upstream search instance per match; reset its PBS for each reroll."""

    def __init__(self, seed: int, search_iters: int = 4, search_depth: int = 1):
        if not available():
            raise RuntimeError("ReBeL source, checkpoint, or PyTorch is unavailable; run make setup-rebel")
        if str(SOURCE) not in sys.path:
            sys.path.insert(0, str(SOURCE))
        import torch
        from game.actions import ActionCodec

        def quantity_only(self, last_action_id):
            if last_action_id < 0:
                return 0, self.liar_action_id
            if last_action_id >= self.liar_action_id:
                return 0, 0
            return ((last_action_id // self.num_faces) + 1) * self.num_faces, self.num_actions

        # The source's codec is shared by its game engine, PBS, and search tree.
        ActionCodec.get_legal_action_range = quantity_only
        from agents.rebel_agent import RebelAgent
        from game.config import GameConfig
        from models.value_net import ValueNet

        torch.set_num_threads(1)
        payload = torch.load(CHECKPOINT, map_location="cpu", weights_only=True)
        expected = {"num_players": 2, "num_dice_per_player": 5, "num_faces": 6,
                    "wild_face_mode": "highest", "hand_representation": "multiset"}
        if payload.get("config_dict") != expected or payload.get("input_size") != 567 or payload.get("output_size") != 252:
            raise RuntimeError("unexpected ReBeL checkpoint configuration")
        net = ValueNet(payload["input_size"], payload["output_size"],
                       payload["n_hidden"], payload["n_layers"])
        net.load_state_dict(payload["model_state_dict"])
        net.eval()
        self.agent = RebelAgent(GameConfig(wild_face_mode="none"), value_net=net,
                                device=torch.device("cpu"), search_depth=search_depth,
                                search_iters=search_iters, seed=seed)
        self.round_number = None
        self.checkpoint_sha256 = hashlib.sha256(CHECKPOINT.read_bytes()).hexdigest()
        self.search_iters = search_iters
        self.search_depth = search_depth

    def act(self, state: dict) -> dict:
        if state["phase"] != "BIDDING":
            raise ValueError("ReBeL requested outside bidding")
        round_number = state["round"]
        if self.round_number != round_number:
            self.agent.reset()
            self.round_number = round_number
        from game.state import PlayerObservation, PublicState
        player = state["turn"]
        own_dice = state["hands"][player]
        if len(own_dice) != 5 or any(not isinstance(d, int) or not 1 <= d <= 6 for d in own_dice):
            raise ValueError("invalid private hand")
        history = tuple(self.agent.codec.encode_bid(e["q"], e["f"] - 1)
                        for e in state["events"] if e.get("round") == round_number and e["type"] == "bid")
        starter = state["starter"]
        # Upstream PBS always begins at its player 0. Reindex seats per round.
        relative_player = 0 if player == starter else 1
        if relative_player != len(history) % 2:
            raise ValueError("public history does not match the active seat")
        own_hand_id = self.agent.hand_space.roll_to_hand_id(tuple(d - 1 for d in own_dice))
        observation = PlayerObservation(
            player_id=relative_player, own_hand_id=own_hand_id,
            own_dice_counts=self.agent.hand_space.get_counts(own_hand_id),
            public_state=PublicState(active_player=relative_player,
                                     last_action_id=history[-1] if history else -1,
                                     history=history))
        self.agent._sync_pbs(observation)
        search = self.agent.solver.solve(root_pbs=self.agent._current_pbs,
                                         max_depth=self.agent.search_depth,
                                         num_iters=self.agent.search_iters,
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
        if result["type"] == "call" and not state["bid"]:
            raise ValueError("ReBeL challenged an opening state")
        if result["type"] == "bid" and state["bid"] and result["q"] <= state["bid"]["q"]:
            raise ValueError("ReBeL made a non-increasing bid")
        return result

    def reset_match(self, seed=None):
        self.agent.reset()
        self.round_number = None
        if seed is not None:
            import numpy as np
            self.agent.rng = np.random.default_rng(seed)
