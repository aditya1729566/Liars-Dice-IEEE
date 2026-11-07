# Fixed-five ruleset

Version: `fixed5_score5_quantity_only_v1`.

Both players keep exactly five six-sided dice for the entire match. At the start of each round, both hands are rolled afresh and privately. The human sees only their hand; public bids, scores, and turn order are visible to both sides. Ones are ordinary dice and there are no wild faces.

A bid `(quantity, face)` says at least that many of the ten dice show that face. The opening bid may claim any quantity from 1 to 10 and any face from 1 to 6. Every later bid must **strictly increase the quantity**; the face may be any value from 1 to 6. The responder may instead challenge. A challenge is mandatory after a quantity-10 bid. There is no exact-match, pass, fold, or reroll action.

On a challenge, both hands are revealed. If the actual face count is at least the quantity, the bidder wins the round; otherwise the challenger wins. The winner gains exactly one point. No die is removed. After a completed round, the human explicitly starts the next round. The previous round's loser opens it, with a fresh five-die hand on each side. The first player to five points wins; a match lasts five to nine rounds. Play Again creates a new match ID and score.
