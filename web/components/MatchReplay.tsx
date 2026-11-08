'use client';

import { useEffect, useRef, useState } from 'react';
import { Die } from './DiceTable';

type Bid = { q: number; f: number };
export type ReplayFrame = {
  step: number;
  kind: 'round_start' | 'bid' | 'call' | 'reveal' | 'next_round' | 'match_end';
  round: number;
  actor: 'HUMAN' | 'AI' | null;
  hands: number[][];
  scores_before: number[];
  scores_after: number[];
  bid: Bid | null;
  previous_bid: Bid | null;
  ai_truth_prior: number | null;
  policy_weight: number | null;
  policy_options: { action: string; weight: number }[];
  decision_source: string | null;
  human_support: number | null;
  ai_support: number | null;
  actual_count: number | null;
  claim_true: boolean | null;
  winner: 'HUMAN' | 'AI' | null;
  ai_read: string;
};

const percent = (value: number | null) => value === null ? '—' : `${(value * 100).toFixed(1)}%`;
const player = (value: 'HUMAN' | 'AI' | null) => value === 'HUMAN' ? 'You' : value === 'AI' ? 'AI' : 'Match';
const claim = (bid: Bid | null) => bid ? `${bid.q} × ${bid.f}` : 'No claim';
const option = (key: string) => key === 'C' ? 'Challenge' : key.replace('-', ' × ');

function title(frame: ReplayFrame) {
  switch (frame.kind) {
    case 'round_start': return `Round ${frame.round} begins`;
    case 'bid': return `${player(frame.actor)} ${frame.previous_bid ? 'raised to' : 'opened with'} ${claim(frame.bid)}`;
    case 'call': return `${player(frame.actor)} challenged ${claim(frame.bid)}`;
    case 'reveal': return `The dice were revealed`;
    case 'next_round': return 'You advanced the match';
    case 'match_end': return `${frame.scores_after[0] === 5 ? 'You won' : 'The AI won'} the match`;
  }
}

function detail(frame: ReplayFrame) {
  if (frame.kind === 'round_start') return `${player(frame.actor)} ${frame.actor === 'HUMAN' ? 'have' : 'has'} the opening turn with a fresh hand. The score was ${frame.scores_before.join('–')}.`;
  if (frame.kind === 'bid') return frame.previous_bid
    ? `The quantity rose from ${frame.previous_bid.q} to ${frame.bid?.q}. The face ${frame.previous_bid.f === frame.bid?.f ? 'stayed the same' : `changed from ${frame.previous_bid.f} to ${frame.bid?.f}`}.`
    : `The first claim of the round was ${claim(frame.bid)}.`;
  if (frame.kind === 'call') return `${player(frame.actor)} challenged the last claim. The hands were counted immediately afterward.`;
  if (frame.kind === 'reveal') return `${frame.actual_count} dice showed ${frame.bid?.f}, against a claim of ${frame.bid?.q}. ${player(frame.winner)} earned one point. The score became ${frame.scores_after.join('–')}.`;
  if (frame.kind === 'next_round') return 'The next round was requested. Both hands were rerolled and the previous round loser opened.';
  return `Final score: ${frame.scores_after.join('–')}.`;
}

export default function MatchReplay({ frames }: { frames: ReplayFrame[] }) {
  const [index, setIndex] = useState(0);
  const slideRef = useRef<HTMLDivElement>(null);
  const firstRender = useRef(true);
  useEffect(() => {
    if (firstRender.current) { firstRender.current = false; return; }
    slideRef.current?.scrollIntoView({ block: 'start' });
  }, [index]);
  if (!frames.length) return <div className="empty-report"><strong>Replay unavailable.</strong><p>This match has no complete event record.</p></div>;
  const frame = frames[Math.min(index, frames.length - 1)];
  const hasClaim = frame.bid !== null;
  const aiMove = frame.actor === 'AI' && (frame.kind === 'bid' || frame.kind === 'call');
  const humanMove = frame.actor === 'HUMAN' && (frame.kind === 'bid' || frame.kind === 'call');
  const scores = frame.kind === 'reveal' || frame.kind === 'match_end' ? frame.scores_after : frame.scores_before;
  const roundStarts = frames.filter(item => item.kind === 'round_start');

  return <section className="replay" aria-label="Complete match replay" tabIndex={0} onKeyDown={event => {
    if (event.key === 'ArrowRight') { event.preventDefault(); setIndex(value => Math.min(value + 1, frames.length - 1)); }
    if (event.key === 'ArrowLeft') { event.preventDefault(); setIndex(value => Math.max(value - 1, 0)); }
  }}>
    <div className="replay-toolbar"><div><p className="eyebrow">COMPLETE MATCH REPLAY</p><h3>Every move, in order.</h3><p>Step through each round, claim, challenge, and reveal. Reads of human intent are hypotheses.</p></div><div className="replay-count"><strong>{String(index + 1).padStart(2, '0')}</strong><span>/ {String(frames.length).padStart(2, '0')}</span></div></div>
    <div className="replay-progress" aria-hidden="true"><i style={{ width: `${((index + 1) / frames.length) * 100}%` }} /></div>
    <div className="replay-rounds" role="group" aria-label="Jump to round">{roundStarts.map(item => <button key={item.round} type="button" className={frame.round === item.round ? 'selected' : ''} onClick={() => setIndex(item.step - 1)}>Round {item.round}</button>)}</div>
    <div className="replay-navigation"><button type="button" onClick={() => setIndex(value => Math.max(value - 1, 0))} disabled={index === 0}>← Previous step</button><span>Use arrow keys while this replay is focused</span><button type="button" onClick={() => setIndex(value => Math.min(value + 1, frames.length - 1))} disabled={index === frames.length - 1}>Next step →</button></div>
    <div className="replay-slide" ref={slideRef} aria-live="polite"><div className="replay-slide-head"><span className={`replay-actor ${frame.actor === 'HUMAN' ? 'human' : frame.actor === 'AI' ? 'ai' : ''}`}>{frame.kind.replaceAll('_', ' ').toUpperCase()} · {player(frame.actor).toUpperCase()}</span><span>ROUND {frame.round} / STEP {index + 1}</span></div>
      <h4>{title(frame)}</h4><p className="replay-summary">{detail(frame)}</p>
      <div className="replay-board"><div className="replay-board-note">POST-MATCH REVEAL <span>The AI only saw its own hand during play.</span></div>
        <div className="replay-hands"><div><span>YOUR FIVE DICE</span><div className="replay-dice">{frame.hands[0].map((die, position) => <Die key={position} value={die} small />)}</div></div><div><span>AI&apos;S FIVE DICE</span><div className="replay-dice">{frame.hands[1].map((die, position) => <Die key={position} value={die} small />)}</div></div></div>
        <div className="replay-board-foot"><div><span>CLAIM IN PLAY</span><strong>{claim(frame.bid)}</strong></div><div><span>SCORE · YOU / AI</span><strong>{scores.join('–')}</strong></div></div>
      </div>
      <div className="replay-analysis"><div className="replay-voice"><span>{humanMove ? 'AI’S READ OF YOUR MOVE' : aiMove ? 'WHY THE AI MADE THIS MOVE' : 'ROUND ANALYSIS'}</span><p>“{frame.ai_read}”</p>{humanMove && <small>Interpretation from public actions and the AI hand. Your intent cannot be known from the game log.</small>}</div>
        {hasClaim && <div className="replay-facts"><div><span>AI TRUTH PRIOR</span><strong>{percent(frame.ai_truth_prior)}</strong><small>Fair unseen dice, before strategic bid evidence</small></div><div><span>ACTUAL COUNT</span><strong>{frame.actual_count} / {frame.bid?.q}</strong><small>{frame.claim_true ? 'Claim was true' : 'Claim was false'}</small></div><div><span>HAND SUPPORT</span><strong>{frame.human_support} / {frame.ai_support}</strong><small>Your dice / AI dice matching face {frame.bid?.f}</small></div>{aiMove && <div><span>POLICY WEIGHT</span><strong>{percent(frame.policy_weight)}</strong><small>{frame.decision_source?.replaceAll('_', ' ') || 'No decision trace'}</small></div>}</div>}
        {aiMove && frame.policy_options.length > 0 && <div className="replay-options"><span>TOP RECORDED POLICY OPTIONS</span>{frame.policy_options.map(item => <div key={item.action}><span>{option(item.action)}</span><strong>{percent(item.weight)}</strong></div>)}</div>}
      </div>
    </div>
    <div className="replay-timeline" role="group" aria-label="All replay steps">{frames.map((item, position) => <button key={item.step} type="button" aria-label={`Step ${item.step}: ${title(item)}`} aria-current={position === index ? 'step' : undefined} className={position === index ? 'current' : ''} onClick={() => setIndex(position)}><span>{String(item.step).padStart(2, '0')}</span><i className={item.actor === 'HUMAN' ? 'human' : item.actor === 'AI' ? 'ai' : ''} /></button>)}</div>
  </section>;
}
