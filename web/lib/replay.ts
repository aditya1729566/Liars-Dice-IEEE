type Bid = { q: number; f: number };
type GameEvent = { type: string; round?: number; from_round?: number; starter?: string; player?: string; sequence?: number; q?: number; f?: number; caller?: string; winner?: string; bid?: Bid; actual?: number; true?: boolean; hands?: number[][]; scores?: number[] };
type Decision = { round: number; sequence: number; action: { type: string }; source?: string; policy_probability?: number | null; policy_options?: unknown[] };
export type ReplayState = { status: string; round: number; scores: number[]; winner: string | null; events: GameEvent[]; ai_decisions?: Decision[] };

const claim = (b: Bid) => `${b.q} × ${b.f}`;
const playerText = (p: string) => p === 'AI' ? 'AI' : 'You';
export function truthPrior(quantity: number, face: number, hand: number[], unknown = 5): number {
  const needed = quantity - hand.filter(d => d === face).length;
  if (needed <= 0) return 1;
  if (needed > unknown) return 0;
  let total = 0;
  for (let k = needed; k <= unknown; k++) {
    let combination = 1;
    for (let j = 1; j <= k; j++) combination *= (unknown - j + 1) / j;
    total += combination * (1 / 6) ** k * (5 / 6) ** (unknown - k);
  }
  return total;
}
function humanBidRead(bid: Bid, previous: Bid | null, aiHand: number[], prior: number): string {
  const opening = previous ? `You raised from ${claim(previous)}` : 'You opened';
  const pace = previous ? (bid.q - previous.q > 1 ? `You skipped ${bid.q - previous.q - 1} possible quantities, which might signal confidence or apply pressure. ` : 'You made the smallest quantity raise. ') : 'As the opener, you had to make a claim.';
  const faceSignal = previous ? (bid.f === previous.f ? 'You kept the face, which might reflect your hand or conceal a bluff.' : 'You changed the face, which might follow your hand or disguise it.') : '';
  const evidence = prior === 1 ? 'My own hand already proves the claim; I did not need to guess your dice.' : prior === 0 ? 'Even five matching unseen dice could not make that claim true.' : prior < .25 ? 'That is unlikely under a fair unseen hand, so a bluff is plausible.' : prior > .65 ? 'That is plausible under a fair unseen hand, but it could still be a bluff.' : 'The fair-dice odds alone leave both an honest bid and a bluff plausible.';
  return `${opening} with ${claim(bid)}. I held ${aiHand.filter(d => d === bid.f).length} matching dice, giving this claim a ${(prior * 100).toFixed(1)}% truth prior before using your choice of bid as evidence. ${pace}${faceSignal} ${evidence} I cannot know your intent.`;
}
function aiActionRead(bid: Bid | null, decision: Decision | undefined, aiHand: number[], prior: number): string {
  if (!decision) return 'This older match has no recorded AI decision trace; its move cannot be explained faithfully.';
  const source = decision.source || 'unknown';
  const weight = decision.policy_probability;
  const selection = source === 'sampled_cfr' && weight != null ? `I sampled this action from my trained policy with ${(weight * 100).toFixed(1)}% weight.` : source === 'uniform_random' ? 'I sampled a legal action uniformly at random.' : source === 'adaptive_public_outcomes' ? 'I used the public-outcome adjustment and probability heuristic for this action.' : source === 'probability_heuristic' ? 'I used the probability heuristic for this action; no trained-policy weight applies.' : `The recorded action source was ${source.replaceAll('_', ' ')}.`;
  if (!bid) return selection;
  return `${selection} I held ${aiHand.filter(d => d === bid.f).length} matching dice. The fair-dice truth prior for ${claim(bid)} was ${(prior * 100).toFixed(1)}%. That prior is not a strategic posterior or a claim about my chance of winning.`;
}

export function buildReplay(state: ReplayState) {
  if (state.status !== 'COMPLETED') throw Error('replay requires a completed match');
  const reveals = new Map(state.events.filter(e => e.type === 'reveal').map(e => [e.round, e]));
  const decisions = new Map((state.ai_decisions || []).map(d => [`${d.round}:${d.sequence}`, d]));
  const calls = new Map((state.ai_decisions || []).filter(d => d.action.type === 'call').map(d => [d.round, d]));
  const slides: Record<string, unknown>[] = [];
  let scores = [0, 0];
  let currentBid: Bid | null = null;
  function add(kind: string, event: GameEvent, actor: string | null = null, bid: Bid | null = null, previousBid: Bid | null = null, decision?: Decision, result?: GameEvent, interpretation = '') {
    const round = event.round ?? event.from_round ?? state.round;
    const hands = reveals.get(round)?.hands;
    if (!hands) throw Error(`missing reveal for round ${round}`);
    const aiHand = hands[1];
    const actual = bid ? hands.flat().filter(d => d === bid.f).length : null;
    slides.push({ step: slides.length + 1, kind, round, actor, hands, scores_before: [...scores], scores_after: result?.scores || [...scores], bid, previous_bid: previousBid, ai_truth_prior: bid ? truthPrior(bid.q, bid.f, aiHand) : null, policy_weight: decision?.policy_probability ?? null, policy_options: decision?.policy_options || [], decision_source: decision?.source || null, human_support: bid ? hands[0].filter(d => d === bid.f).length : null, ai_support: bid ? aiHand.filter(d => d === bid.f).length : null, actual_count: actual, claim_true: bid ? actual! >= bid.q : null, winner: result?.winner || null, ai_read: interpretation });
  }
  for (const event of state.events) {
    const kind = event.type;
    if (kind === 'round_start') {
      scores = [...(event.scores || scores)]; currentBid = null;
      const starter = event.starter || 'HUMAN';
      add(kind, event, starter, null, null, undefined, undefined, `A new hand was rolled. ${playerText(starter)} ${starter === 'HUMAN' ? 'have' : 'has'} the opening turn. I could see my five dice, but not yours.`);
    } else if (kind === 'bid') {
      const bid = { q: event.q!, f: event.f! };
      const previous = currentBid;
      const decision = event.player === 'AI' ? decisions.get(`${event.round}:${event.sequence}`) : undefined;
      const aiHand = reveals.get(event.round)?.hands?.[1];
      if (!aiHand) throw Error('missing reveal hand');
      const prior = truthPrior(bid.q, bid.f, aiHand);
      const read = event.player === 'HUMAN' ? humanBidRead(bid, previous, aiHand, prior) : aiActionRead(bid, decision, aiHand, prior);
      add(kind, event, event.player || null, bid, previous, decision, undefined, read);
      currentBid = bid;
    } else if (kind === 'reveal') {
      if (!currentBid || !event.hands) throw Error('missing challenge bid or hands');
      const caller = event.caller || 'HUMAN';
      const decision = caller === 'AI' ? calls.get(event.round ?? -1) : undefined;
      const prior = truthPrior(currentBid.q, currentBid.f, event.hands[1]);
      const read = caller === 'HUMAN' ? `You challenged ${claim(currentBid)}. I could see my own hand and a ${(prior * 100).toFixed(1)}% fair-dice truth prior. You might have seen too few matching dice in your hand or suspected my bidding pattern, but I cannot know your reason from the challenge alone.` : aiActionRead(currentBid, decision, event.hands[1], prior);
      add('call', event, caller, currentBid, currentBid, decision, undefined, read);
      add('reveal', event, null, currentBid, currentBid, undefined, event, `Both hands are now visible. ${event.actual} dice showed ${currentBid.f}; ${claim(currentBid)} was ${event.true ? 'true' : 'false'}. ${playerText(event.winner || 'HUMAN')} scored one point.`);
      scores = [...(event.scores || scores)];
    } else if (kind === 'next_round') {
      add(kind, event, 'HUMAN', currentBid, null, undefined, undefined, 'You selected Next round. The previous round\'s loser opens after both hands reroll.');
    } else if (kind === 'match_end') {
      add(kind, { type: kind, round: state.round }, null, currentBid, null, undefined, undefined, `The match ended ${scores[0]}–${scores[1]}. ${playerText(event.winner || 'HUMAN')} reached five points.`);
    }
  }
  return slides;
}
