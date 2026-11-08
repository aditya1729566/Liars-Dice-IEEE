"""Build a post-match, event-by-event analysis from authoritative match state.

Interpretations of human intent use only the AI hand and public actions. They are
explicit hypotheses, not a hidden reasoning trace or a strategic posterior.
"""

from math import comb


def truth_prior(quantity, face, hand, unknown=5):
    needed = quantity - hand.count(face)
    if needed <= 0:
        return 1.0
    if needed > unknown:
        return 0.0
    return sum(comb(unknown, k) * (1 / 6) ** k * (5 / 6) ** (unknown - k)
               for k in range(needed, unknown + 1))


def claim_text(bid):
    return f"{bid['q']} × {bid['f']}"


def player_text(player):
    return "AI" if player == "AI" else "You"


def human_bid_read(bid, previous, ai_hand, prior):
    opening = "You opened" if previous is None else f"You raised from {claim_text(previous)}"
    if previous is None:
        move_signal = "As the opener, you had to make a claim."
    else:
        jump = bid["q"] - previous["q"]
        pace = (f"You skipped {jump - 1} possible quantities, which might signal confidence or apply pressure. "
                if jump > 1 else "You made the smallest quantity raise. ")
        face_signal = ("You kept the face, which might reflect your hand or conceal a bluff."
                       if bid["f"] == previous["f"] else
                       "You changed the face, which might follow your hand or disguise it.")
        move_signal = pace + face_signal
    evidence = ("My own hand already proves the claim; I did not need to guess your dice."
                if prior == 1.0 else
                "Even five matching unseen dice could not make that claim true."
                if prior == 0.0 else
                "That is unlikely under a fair unseen hand, so a bluff is plausible."
                if prior < 0.25 else
                "That is plausible under a fair unseen hand, but it could still be a bluff."
                if prior > 0.65 else
                "The fair-dice odds alone leave both an honest bid and a bluff plausible.")
    return (f"{opening} with {claim_text(bid)}. I held {ai_hand.count(bid['f'])} "
            f"matching dice, giving this claim a {prior * 100:.1f}% truth prior before "
            f"using your choice of bid as evidence. {move_signal} {evidence} I cannot know your intent.")


def ai_action_read(kind, bid, decision, ai_hand, prior):
    if decision is None:
        return "This older match has no recorded AI decision trace; its move cannot be explained faithfully."
    source = decision.get("source", "unknown")
    weight = decision.get("policy_probability")
    if source == "sampled_cfr" and weight is not None:
        selection = f"I sampled this action from my trained policy with {weight * 100:.1f}% weight."
    elif source == "uniform_random":
        selection = "I sampled a legal action uniformly at random."
    elif source == "adaptive_public_outcomes":
        selection = "I used the public-outcome adjustment and probability heuristic for this action."
    elif source == "probability_heuristic":
        selection = "I used the probability heuristic for this action; no trained-policy weight applies."
    else:
        selection = f"The recorded action source was {source.replace('_', ' ')}."
    if bid is None:
        return selection
    return (f"{selection} I held {ai_hand.count(bid['f'])} matching dice. "
            f"The fair-dice truth prior for {claim_text(bid)} was {prior * 100:.1f}%. "
            "That prior is not a strategic posterior or a claim about my chance of winning.")


def build_replay(state):
    """Return slides covering every event, with a separate challenge slide."""
    if state.get("status") != "COMPLETED":
        raise ValueError("replay requires a completed match")
    reveals = {event["round"]: event for event in state["events"] if event["type"] == "reveal"}
    decisions = {(d["round"], d["sequence"]): d for d in state.get("ai_decisions", [])}
    calls = {d["round"]: d for d in state.get("ai_decisions", []) if d["action"]["type"] == "call"}
    slides = []
    scores = [0, 0]
    current_bid = None

    def add(kind, event, actor=None, bid=None, previous_bid=None, decision=None,
            result=None, interpretation=""):
        round_index = event.get("round", event.get("from_round", state["round"]))
        hands = reveals[round_index]["hands"]
        ai_hand = hands[1]
        prior = truth_prior(bid["q"], bid["f"], ai_hand) if bid else None
        actual = sum(die == bid["f"] for hand in hands for die in hand) if bid else None
        slide = {
            "step": len(slides) + 1,
            "kind": kind,
            "round": round_index,
            "actor": actor,
            "hands": hands,
            "scores_before": scores.copy(),
            "scores_after": result["scores"] if result else scores.copy(),
            "bid": bid,
            "previous_bid": previous_bid,
            "ai_truth_prior": prior,
            "policy_weight": decision.get("policy_probability") if decision else None,
            "policy_options": decision.get("policy_options", []) if decision else [],
            "decision_source": decision.get("source") if decision else None,
            "human_support": hands[0].count(bid["f"]) if bid else None,
            "ai_support": ai_hand.count(bid["f"]) if bid else None,
            "actual_count": actual,
            "claim_true": actual >= bid["q"] if bid else None,
            "winner": result["winner"] if result else None,
            "ai_read": interpretation,
        }
        slides.append(slide)

    for event in state["events"]:
        kind = event["type"]
        if kind == "round_start":
            scores = event["scores"][:]
            current_bid = None
            starter = event["starter"]
            add(kind, event, starter, interpretation=(
                f"A new hand was rolled. {player_text(starter)} "
                f"{'have' if starter == 'HUMAN' else 'has'} the opening turn. "
                "I could see my five dice, but not yours."))
        elif kind == "bid":
            bid = {"q": event["q"], "f": event["f"]}
            previous = current_bid
            decision = decisions.get((event["round"], event["sequence"])) if event["player"] == "AI" else None
            prior = truth_prior(bid["q"], bid["f"], reveals[event["round"]]["hands"][1])
            read = (human_bid_read(bid, previous, reveals[event["round"]]["hands"][1], prior)
                    if event["player"] == "HUMAN" else
                    ai_action_read(kind, bid, decision, reveals[event["round"]]["hands"][1], prior))
            add(kind, event, event["player"], bid, previous, decision, interpretation=read)
            current_bid = bid
        elif kind == "reveal":
            caller = event["caller"]
            decision = calls.get(event["round"]) if caller == "AI" else None
            ai_hand = event["hands"][1]
            prior = truth_prior(current_bid["q"], current_bid["f"], ai_hand)
            if caller == "HUMAN":
                read = (f"You challenged {claim_text(current_bid)}. I could see my own hand and "
                        f"a {prior * 100:.1f}% fair-dice truth prior. You might have seen too few "
                        "matching dice in your hand or suspected my bidding pattern, but I cannot "
                        "know your reason from the challenge alone.")
            else:
                read = ai_action_read("call", current_bid, decision, ai_hand, prior)
            add("call", event, caller, current_bid, current_bid, decision, interpretation=read)
            add("reveal", event, None, current_bid, current_bid, result=event,
                interpretation=(f"Both hands are now visible. {event['actual']} dice showed "
                                f"{current_bid['f']}; {claim_text(current_bid)} was "
                                f"{'true' if event['true'] else 'false'}. {player_text(event['winner'])} scored one point."))
            scores = event["scores"][:]
        elif kind == "next_round":
            add(kind, event, "HUMAN", current_bid,
                interpretation="You selected Next round. The previous round's loser opens after both hands reroll.")
        elif kind == "match_end":
            add(kind, {"round": state["round"]}, None, current_bid,
                interpretation=f"The match ended {scores[0]}–{scores[1]}. {player_text(event['winner'])} reached five points.")
    return slides
