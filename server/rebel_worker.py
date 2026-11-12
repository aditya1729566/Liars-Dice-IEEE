"""Persistent local ReBeL inference worker; one policy state per match."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from rebel_bridge import RebelPolicy

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
                    policies[match_id] = RebelPolicy(seed=request["seed"])
                policy = policies[match_id]
                action = policy.act(request["observation"])
                result = {"action": action, "metadata": policy.last_metadata}
                replies[match_id] = (version, result)
    except Exception as exc:
        result = {"error": f"{type(exc).__name__}: {exc}"}
    print(json.dumps(result, separators=(",", ":")), flush=True)
