"""Persistent inference worker for the updated BLUFF.EXE ReBeL checkpoint."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from rebel_v2_bridge import RebelV2Policy

policies = {}
replies = {}
for line in sys.stdin:
    try:
        request = json.loads(line)
        match_id = request["match_id"]
        if request.get("op") == "drop":
            policies.pop(match_id, None)
            replies.pop(match_id, None)
            result = {"ok": True}
        else:
            version = request["observation"].get("version")
            cached = replies.get(match_id)
            if cached is not None and cached[0] == version:
                result = cached[1]
            else:
                if match_id not in policies:
                    policies[match_id] = RebelV2Policy(seed=request["seed"],
                                                        search_iters=request.get("search_iters", 32),
                                                        search_depth=request.get("search_depth", 1))
                policy = policies[match_id]
                action = policy.act(request["observation"])
                result = {"action": action, "metadata": policy.last_metadata}
                replies[match_id] = (version, result)
    except Exception as exc:
        result = {"error": f"{type(exc).__name__}: {exc}"}
    print(json.dumps(result, separators=(",", ":")), flush=True)
