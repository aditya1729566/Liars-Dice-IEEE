'use client';

import { useEffect, useMemo, useState } from 'react';
import DiceTable, { Die } from '../components/DiceTable';
import MatchReplay, { type ReplayFrame } from '../components/MatchReplay';

const API = '';
type Bid = { q: number; f: number };
type Action = { type: 'bid'; q: number; f: number } | { type: 'call' };
type Event = { type: string; round?: number; player?: string; q?: number; f?: number; bid?: Bid; actual?: number; true?: boolean; winner?: string; caller?: string; hands?: number[][] };
type Game = { id: string; duration_seconds: number; scores: number[]; round: number; phase: 'BIDDING' | 'ROUND_OVER' | 'MATCH_OVER'; status: 'ACTIVE' | 'COMPLETED'; turn: string; bid: Bid | null; winner: string | null; version: number; agent: string; hand: number[]; ai_hand: number[] | null; events: Event[]; legal_actions: Action[] };
type Decision = { round: number; sequence: number; scores: number[]; hand: number[]; current_bid: Bid | null; current_bid_truth_prior: number | null; action: Action; action_truth_prior: number | null; source: string; policy_probability: number | null; policy_options?: { action: string; weight: number }[]; policy_key: string | null; policy_id: string };
type MatchReport = { id: string; agent: string; winner: string; scores: number[]; rounds: number; decisions: Decision[]; reveals: Event[]; replay: ReplayFrame[]; method: string };
type ResearchRun = { run_id: string; completed_matches: number; warning?: string; provenance?: { seed_offset?: number; engine_sha256?: string; policy_sha256?: string; policy_sha256_by_file?: Record<string, string> }; results: Record<string, { wins: number; matches: number; win_rate: number; wilson95: number[] }>; mccfr_metrics?: { opponents: Record<string, { paired_seed_cluster95?: number[] }> }; mccfr_v2_metrics?: { opponents: Record<string, { paired_seed_cluster95?: number[]; policy_coverage?: number }> }; rebel_metrics?: { opponents: Record<string, { paired_seed_cluster95?: number[]; policy_coverage?: number }> }; rebel_v2_metrics?: { opponents: Record<string, { paired_seed_cluster95?: number[]; policy_coverage?: number }> } };
type Analysis = { naive_prior_from_ai_hand: number };
const agents = [
  { id: 'cfr2', name: 'The Apprentice', detail: 'Wider trained strategy' },
  { id: 'mccfr_external_v1', name: 'The Monte Carlo', detail: 'External-Sampling MCCFR · explores sampled scenarios to minimize regret' },
  { id: 'mccfr_external_v2', name: 'The Monte Carlo II', detail: 'Current champion · wider bids · public history' },
  { id: 'rebel_transfer_v1', name: 'The ReBeL Transfer', detail: 'Depth-one public-belief search · local runtime' },
  { id: 'rebel_bluff_v2', name: 'The ReBeL BLUFF.EXE', detail: 'Updated native checkpoint · local runtime' },
  { id: 'probability', name: 'The Calculator', detail: 'Exact odds for five unseen dice' },
  { id: 'adaptive', name: 'The Observer', detail: 'Public outcomes · experimental' },
  { id: 'aggressive', name: 'The Bluffer', detail: 'Pushes the quantity upward' },
  { id: 'random', name: 'The Wildcard', detail: 'Samples every legal move' },
];
const labelFor = (id: string) => id === 'cfr' ? 'The Apprentice (original)' : agents.find(a => a.id === id)?.name || id;
const pct = (p: number | null) => p === null ? '—' : `${(p * 100).toFixed(1)}%`;
function BenchmarkComparison({ runs }: { runs: ResearchRun[] }) {
  const final = runs.find(run => run.run_id === 'mccfr_confirm_2000_20261112') || runs.find(run => run.run_id === 'mccfr_final_20261112');
  if (!final) return null;
  const seat0 = final.results.mccfr_external_v1_vs_cfr2_seat_0;
  const seat1 = final.results.mccfr_external_v1_vs_cfr2_seat_1;
  if (!seat0 || !seat1) return null;
  const wins = seat0.wins + seat1.wins;
  const matches = seat0.matches + seat1.matches;
  const p = wins / matches;
  const z = 1.96;
  const denominator = 1 + z * z / matches;
  const center = (p + z * z / (2 * matches)) / denominator;
  const radius = z * Math.sqrt(p * (1 - p) / matches + z * z / (4 * matches * matches)) / denominator;
  const paired = final.mccfr_metrics?.opponents.cfr2?.paired_seed_cluster95;
  const interval = paired || [center - radius, center + radius];
  const intervalLabel = paired ? '95% paired-seed interval' : '95% Wilson interval';
  const precisePct = (value: number) => `${(100 * value).toFixed(2)}%`;
  const v2 = runs.find(run => run.run_id === 'mccfr_v2_final_major_20261112');
  const v2Seat0 = v2?.results.mccfr_external_v2_vs_mccfr_external_v1_seat_0;
  const v2Seat1 = v2?.results.mccfr_external_v2_vs_mccfr_external_v1_seat_1;
  const v2Wins = (v2Seat0?.wins ?? 0) + (v2Seat1?.wins ?? 0);
  const v2Matches = (v2Seat0?.matches ?? 0) + (v2Seat1?.matches ?? 0);
  const v2Interval = v2?.mccfr_v2_metrics?.opponents.mccfr_external_v1?.paired_seed_cluster95;
  return <><div className="evidence-run" aria-label="Measured MCCFR versus Apprentice comparison">
    <div className="evidence-run-head"><strong>Monte Carlo vs Apprentice</strong><span>final holdout</span></div>
    <p>{wins} wins in {matches} paired-seed, seat-balanced matches ({precisePct(p)}; {intervalLabel} {precisePct(interval[0])}–{precisePct(interval[1])}). Both policies use one-round abstractions.</p>
  </div>{v2Matches > 0 && v2Interval && <div className="evidence-run" aria-label="Measured Monte Carlo II versus Monte Carlo comparison"><div className="evidence-run-head"><strong>Monte Carlo II vs Monte Carlo</strong><span>held-out matches</span></div><p>{v2Wins} wins in {v2Matches} paired-seed, seat-balanced matches ({precisePct(v2Wins / v2Matches)}; 95% paired-seed interval {precisePct(v2Interval[0])}–{precisePct(v2Interval[1])}). Learned-policy coverage {pct(v2?.mccfr_v2_metrics?.opponents.mccfr_external_v1?.policy_coverage ?? null)}.</p></div>}</>;
}
function RebelComparison({ runs }: { runs: ResearchRun[] }) {
  const run = runs.find(item => item.run_id === 'rebel_transfer_final_20261112');
  const first = run?.results.rebel_transfer_v1_vs_mccfr_external_v2_seat_0;
  const second = run?.results.rebel_transfer_v1_vs_mccfr_external_v2_seat_1;
  const interval = run?.rebel_metrics?.opponents.mccfr_external_v2?.paired_seed_cluster95;
  if (!first || !second) return null;
  const wins = first.wins + second.wins;
  const matches = first.matches + second.matches;
  return <div className="evidence-run" aria-label="Measured ReBeL Transfer versus Monte Carlo II comparison">
    <div className="evidence-run-head"><strong>ReBeL Transfer vs Monte Carlo II</strong><span>held-out transfer test</span></div>
    <p>{wins} wins in {matches} paired-seed, seat-balanced matches ({pct(wins / matches)}{interval ? `; approximate 95% paired-seed interval ${pct(interval[0])}–${pct(interval[1])}` : ''}). Its checkpoint was trained with wild sixes and a different bid order. This result measures transfer under this table’s rules.</p>
  </div>;
}
function RebelNativeComparison({ runs }: { runs: ResearchRun[] }) {
  const run = runs.find(item => item.run_id === 'rebel_bluff_v2_final_random_20261114');
  if (!run) return null;
  return <div className="evidence-run" aria-label="Measured updated ReBeL comparisons">
    <div className="evidence-run-head"><strong>Updated ReBeL BLUFF.EXE</strong><span>seat-balanced holdout</span></div>
    {(['mccfr_external_v2', 'rebel_transfer_v1', 'probability'] as const).map(opponent => {
      const first = run.results[`rebel_bluff_v2_vs_${opponent}_seat_0`];
      const second = run.results[`rebel_bluff_v2_vs_${opponent}_seat_1`];
      if (!first || !second) return null;
      const wins = first.wins + second.wins;
      const matches = first.matches + second.matches;
      const interval = run.rebel_v2_metrics?.opponents[opponent]?.paired_seed_cluster95;
      return <p key={opponent}>{labelFor(opponent)}: {wins}/{matches} wins ({pct(wins / matches)}{interval ? `; 95% paired-seed interval ${pct(interval[0])}–${pct(interval[1])}` : ''}).</p>;
    })}
    <p>Uses a native no-wild, quantity-only checkpoint. Upstream training alternated round openers; this table gives the next opening move to the round loser.</p>
  </div>;
}
async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(API + path, { ...options, headers: { 'Content-Type': 'application/json', ...options?.headers } });
  const body = await response.json();
  if (!response.ok) throw Error(body.error || `HTTP ${response.status}`);
  return body as T;
}

function Score({ scores }: { scores: number[] }) {
  return <div className="scoreboard" aria-label={`Score: you ${scores[0]}, AI ${scores[1]}. First to five points.`}>
    {(['YOU', 'AI'] as const).map((side, i) => <div className="score-side" key={side}><div><span>{side}</span><strong>{scores[i]}</strong></div><div className="score-ticks" aria-hidden="true">{Array.from({ length: 5 }, (_, n) => <i key={n} className={n < scores[i] ? 'won' : ''} />)}</div></div>)}
    <span className="score-target">FIRST TO 5</span>
  </div>;
}

export default function Home() {
  const [game, setGame] = useState<Game | null>(null);
  const [agent, setAgent] = useState('mccfr_external_v2');
  const [quantity, setQuantity] = useState(1);
  const [face, setFace] = useState(1);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [tab, setTab] = useState<'play' | 'research' | 'system'>('play');
  const [tutorial, setTutorial] = useState(false);
  const [tutorialStep, setTutorialStep] = useState(0);
  const [roundAnalysis, setRoundAnalysis] = useState<Analysis | null>(null);
  const [runs, setRuns] = useState<ResearchRun[]>([]);
  const [health, setHealth] = useState<{ ok: boolean; policy_ok: boolean } | null>(null);
  const [rebelAvailable, setRebelAvailable] = useState<Record<string, boolean>>({});
  const [leaderboard, setLeaderboard] = useState<{ completed_matches: number; human_wins: number; ai_wins: number } | null>(null);
  const [completedIds, setCompletedIds] = useState<string[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [report, setReport] = useState<MatchReport | null>(null);
  const [reportError, setReportError] = useState('');

  const legalBids = (game?.legal_actions || []).filter((a): a is { type: 'bid'; q: number; f: number } => a.type === 'bid');
  const selectedBid = legalBids.find(a => a.q === quantity && a.f === face);
  const canCall = game?.legal_actions.some(a => a.type === 'call') || false;
  const lastReveal = useMemo(() => [...(game?.events || [])].reverse().find(e => e.type === 'reveal'), [game]);
  const currentBids = (game?.events || []).filter(e => e.type === 'bid' && e.round === game?.round);

  useEffect(() => {
    const saved = sessionStorage.getItem('bluff_match');
    if (saved) request<Game>(`/api/matches/${saved}`).then(setGame).catch(() => sessionStorage.removeItem('bluff_match'));
    try { setCompletedIds(JSON.parse(sessionStorage.getItem('bluff_completed_matches') || '[]')); } catch { setCompletedIds([]); }
  }, []);
  useEffect(() => {
    request<{ runs: ResearchRun[] }>('/api/research/summary').then(data => setRuns(data.runs)).catch(() => {});
    request<{ ok: boolean; policy_ok: boolean }>('/api/health').then(setHealth).catch(() => setHealth({ ok: false, policy_ok: false }));
    request<{ agents: { id: string; available: boolean }[] }>('/api/agents').then(data => setRebelAvailable(Object.fromEntries(data.agents.map(item => [item.id, item.available])))).catch(() => setRebelAvailable({}));
    request<typeof leaderboard>('/api/leaderboard').then(setLeaderboard).catch(() => {});
  }, [game?.status]);
  useEffect(() => {
    if (game?.status !== 'COMPLETED') return;
    setCompletedIds(old => {
      if (old.includes(game.id)) return old;
      const updated = [game.id, ...old];
      sessionStorage.setItem('bluff_completed_matches', JSON.stringify(updated));
      return updated;
    });
  }, [game?.id, game?.status]);
  useEffect(() => {
    if (tab !== 'research' || !selectedId) return;
    let cancelled = false;
    setReport(null);
    setReportError('');
    request<MatchReport>(`/api/matches/${selectedId}/research`).then(data => { if (!cancelled) { setReport(data); setReportError(''); } }).catch(e => { if (!cancelled) { setReport(null); setReportError(String(e)); } });
    return () => { cancelled = true; };
  }, [tab, selectedId]);
  useEffect(() => {
    const bids = (game?.legal_actions || []).filter((a): a is { type: 'bid'; q: number; f: number } => a.type === 'bid');
    if (bids.length && !bids.some(a => a.q === quantity && a.f === face)) { setQuantity(bids[0].q); setFace(bids[0].f); }
  }, [game?.legal_actions, quantity, face]);
  useEffect(() => {
    if (game?.id && lastReveal?.round && game.phase !== 'BIDDING') request<Analysis>(`/api/matches/${game.id}/analysis/${lastReveal.round}`).then(setRoundAnalysis).catch(() => setRoundAnalysis(null));
    else setRoundAnalysis(null);
  }, [game?.id, game?.phase, lastReveal?.round]);

  async function start() { setBusy(true); setError(''); try { const next = await request<Game>('/api/matches', { method: 'POST', body: JSON.stringify({ n: 5, agent }) }); setGame(next); setQuantity(1); setFace(1); sessionStorage.setItem('bluff_match', next.id); setTab('play'); } catch (e) { setError(String(e)); } finally { setBusy(false); } }
  async function act(action: Action) { if (!game) return; setBusy(true); setError(''); try { setGame(await request<Game>(`/api/matches/${game.id}/actions`, { method: 'POST', body: JSON.stringify({ action, expected_version: game.version, idempotency_key: crypto.randomUUID() }) })); } catch (e) { setError(String(e)); } finally { setBusy(false); } }
  async function nextRound() { if (!game) return; setBusy(true); setError(''); try { setGame(await request<Game>(`/api/matches/${game.id}/next-round`, { method: 'POST', body: JSON.stringify({ expected_version: game.version, idempotency_key: crypto.randomUUID() }) })); setQuantity(1); setFace(1); } catch (e) { setError(String(e)); } finally { setBusy(false); } }
  async function deleteMatch() { if (game) { try { await request(`/api/matches/${game.id}`, { method: 'DELETE' }); setCompletedIds(old => { const next = old.filter(id => id !== game.id); sessionStorage.setItem('bluff_completed_matches', JSON.stringify(next)); return next; }); if (selectedId === game.id) { setSelectedId(null); setReport(null); } } catch (e) { setError(String(e)); return; } } sessionStorage.removeItem('bluff_match'); setGame(null); setTab('play'); }
  function playAgain() { sessionStorage.removeItem('bluff_match'); setGame(null); setTab('play'); }
  function openReport() { if (game) setSelectedId(game.id); setTab('research'); }

  return <main className="app-shell">
    <header className="site-header"><div className="brand"><span className="brand-mark">B.</span><span>BLUFF.EXE<small>FIVE DICE · FIRST TO FIVE</small></span></div><nav aria-label="Main navigation"><button className={tab === 'play' ? 'active' : ''} onClick={() => setTab('play')}>Play</button><button className={tab === 'research' ? 'active' : ''} onClick={() => { setSelectedId(id => id || completedIds[0] || null); setTab('research'); }}>Research</button><button className={tab === 'system' ? 'active' : ''} onClick={() => setTab('system')}>System</button></nav><span className={`connection ${health?.ok ? 'online' : ''}`}>{health === null ? 'Checking' : health.ok ? 'Game online' : 'Game offline'}</span></header>

    {tab === 'play' ? <div className="play-layout"><section className="play-main"><div className="page-intro"><div><p className="eyebrow">HUMAN VS MACHINE</p><h1>{game ? game.status === 'COMPLETED' ? 'Match complete.' : 'Read the table.' : 'Call the bluff.'}</h1><p>{game ? 'Five dice each. The next claim must name more dice, or you can challenge.' : 'One hidden hand. One rising claim. Decide when the AI is bluffing.'}</p></div><button className="quiet-button" onClick={() => { setTutorialStep(0); setTutorial(true); }}>How to play <span aria-hidden="true">↗</span></button></div><Score scores={game?.scores || [0, 0]} /><div className="table-shell"><div className="table-topline"><span>{game ? `ROUND ${String(game.round).padStart(2, '0')}` : 'TABLE PREVIEW'}</span><span>{game?.phase === 'BIDDING' ? 'BIDDING' : game?.phase === 'ROUND_OVER' ? 'DICE REVEALED' : game?.status === 'COMPLETED' ? 'FINAL SCORE' : 'NO WILD DICE'}</span></div><DiceTable hand={game?.hand || [1, 2, 3, 4, 5]} aiHand={game?.phase === 'BIDDING' ? null : game?.ai_hand} bid={game?.bid} round={game?.round} /></div><div className="table-status" aria-live="polite"><span className="status-dot" />{game?.status === 'COMPLETED' ? `${game.winner === 'HUMAN' ? 'You won' : 'The AI won'} · final score ${game.scores.join('–')}` : game?.phase === 'ROUND_OVER' ? 'Round decided · review the revealed dice' : game ? 'Your turn · raise or challenge' : 'Sample dice shown · start a match to roll'}</div></section>
      <aside className="control-panel">{!game ? <><div className="panel-heading"><p className="eyebrow">NEW MATCH</p><h2>Choose an opponent</h2><p>Every agent plays the same five-dice rules. You can replay every move after the match.</p></div><div className="agent-list" role="radiogroup" aria-label="AI opponent">{agents.map(item => <button key={item.id} type="button" role="radio" aria-checked={agent === item.id} className={agent === item.id ? 'chosen' : ''} disabled={item.id.startsWith('rebel_') && !rebelAvailable[item.id]} onClick={() => setAgent(item.id)}><span className="radio-mark" /><span><strong>{item.name}</strong><small>{item.id.startsWith('rebel_') && !rebelAvailable[item.id] ? 'Available after local ReBeL setup' : item.detail}</small></span></button>)}</div><button className="primary-action" onClick={start} disabled={busy}>{busy ? 'Starting…' : 'Start match'} <span aria-hidden="true">→</span></button></> : <><div className="panel-heading"><p className="eyebrow">{labelFor(game.agent)} · ROUND {game.round}</p><h2>{game.status === 'COMPLETED' ? game.winner === 'HUMAN' ? 'You won the match.' : 'The AI won the match.' : game.phase === 'ROUND_OVER' ? 'The dice are out.' : 'Your move.'}</h2><p>{game.status === 'COMPLETED' ? 'The final score is locked. Review how the AI played, or start again.' : game.phase === 'ROUND_OVER' ? 'One point went to the round winner. The loser opens next.' : 'Raise the quantity or challenge. Changing only the face is not a raise.'}</p></div>{game.phase === 'BIDDING' ? <><div className="current-bid"><span>CURRENT CLAIM</span><strong>{game.bid ? <>{game.bid.q} <span>×</span> <Die value={game.bid.f} small /></> : 'No claim yet'}</strong></div><div className="selectors"><label>QUANTITY<select value={quantity} onChange={e => setQuantity(Number(e.target.value))}>{Array.from(new Set(legalBids.map(a => a.q))).map(value => <option key={value} value={value}>{value}</option>)}</select></label><label>DIE FACE<select value={face} onChange={e => setFace(Number(e.target.value))}>{[1, 2, 3, 4, 5, 6].map(value => <option key={value} value={value}>{value}</option>)}</select></label></div><p className="legal-note">{selectedBid ? `Your bid: ${quantity} ${quantity === 1 ? 'die' : 'dice'} showing ${face}` : 'Choose a higher quantity.'}</p><button className="primary-action" disabled={busy || !selectedBid} onClick={() => selectedBid && act(selectedBid)}>{busy ? 'Waiting…' : 'Raise the bid'} <span aria-hidden="true">→</span></button><button className="call-action" disabled={busy || !canCall} onClick={() => act({ type: 'call' })}>Challenge the claim <span aria-hidden="true">→</span></button></> : <><div className="reveal-notice"><span>ROUND {game.round} RESULT</span><strong>{lastReveal?.true ? 'The claim held.' : 'The claim was false.'}</strong><p>{lastReveal?.winner === 'HUMAN' ? 'You earned' : 'The AI earned'} one point. {lastReveal?.actual} {lastReveal?.actual === 1 ? 'die' : 'dice'} showed {lastReveal?.bid?.f}; {lastReveal?.bid?.q} were claimed.</p>{roundAnalysis && <small>The AI’s prior for that claim was {pct(roundAnalysis.naive_prior_from_ai_hand)} before considering the bid.</small>}</div>{game.phase === 'ROUND_OVER' ? <button className="primary-action" disabled={busy} onClick={nextRound}>Next round <span aria-hidden="true">→</span></button> : <><button className="primary-action" onClick={openReport}>Replay the match <span aria-hidden="true">→</span></button><button className="secondary-action" onClick={playAgain}>Play again</button></>}</>}{game.status !== 'COMPLETED' && <div className="bid-history"><h3>Public claims <span>ROUND {game.round}</span></h3>{currentBids.length ? currentBids.map((event, index) => <div key={index}><span>{event.player === 'HUMAN' ? 'You' : 'AI'}</span><strong>{event.q} × {event.f}</strong></div>) : <p>No claims yet.</p>}</div>}</>}</aside></div> : tab === 'research' ? <section className="info-page research-page"><div className="page-intro"><div><p className="eyebrow">MATCH RESEARCH</p><h1>Every move, explained.</h1><p>Step through completed matches in this browser session. See both hands, every action, and what the AI could infer at the time.</p></div></div><div className="research-layout"><div className="research-main"><div className="section-head"><h2>Completed matches</h2><span>{completedIds.length} completed</span></div>{completedIds.length ? <div className="report-picker" role="group" aria-label="Completed matches">{completedIds.map((id, index) => <button key={id} className={selectedId === id ? 'selected' : ''} onClick={() => setSelectedId(id)}>Match {completedIds.length - index}<small>{id.slice(0, 7)}</small></button>)}</div> : <div className="empty-report"><strong>No completed match yet.</strong><p>Finish a match and its AI decision record will appear here.</p><button className="secondary-action" onClick={() => setTab('play')}>Go to the table</button></div>}{reportError && <p role="alert" className="error-inline">{reportError}</p>}{report && <><div className="report-summary"><div><span>RESULT</span><strong>{report.winner === 'HUMAN' ? 'You won' : 'AI won'} · {report.scores.join('–')}</strong></div><div><span>OPPONENT</span><strong>{labelFor(report.agent)}</strong></div><div><span>AI DECISIONS</span><strong>{report.decisions.length}</strong></div></div><MatchReplay key={report.id} frames={report.replay} /><details className="method-details"><summary>How this replay was made</summary><p>{report.method} A policy weight is the trained mix for an AI action, not its chance of winning. The replay shows both hands only because the match is over.</p></details></>}</div><aside className="research-aside"><div className="section-head"><h2>The models</h2></div><p>The Apprentice uses a sampled one-round policy over a restricted set of raises. The Monte Carlo uses external-sampling MCCFR: it samples dice and opponent actions, explores its own possible replies, and accumulates regret. Both use abstractions and neither sees your hidden dice.</p><p>The Monte Carlo optimizes a round point. The Monte Carlo II has wider bids, uses a small signal from older public claims, and trains with a depth-limited first-to-five value. It backs off to a learned coarse policy for unseen fine states. Both retain imperfect recall, and neither has a five-dice equilibrium guarantee. The ReBeL Transfer uses a checkpoint trained with wild sixes and face-ordered raises. The updated ReBeL BLUFF.EXE checkpoint was trained with quantity-only bids and no wild dice, then searches under this table’s rules. Its upstream training engine alternates the next opener, while this table has the round loser open next. Both ReBeL models require the local PyTorch runtime. The measured comparisons below show completed matches.</p><BenchmarkComparison runs={runs} /><RebelComparison runs={runs} /><RebelNativeComparison runs={runs} /><details className="evaluation-details"><summary>Measured evaluations <span>{runs.length} runs</span></summary>{runs.map(run => <div className="evidence-run" key={run.run_id}><div className="evidence-run-head"><strong>{run.run_id.replaceAll('_', ' ')}</strong><span>{run.completed_matches} matches</span></div>{run.warning && <p className="run-warning">{run.warning}</p>}<small>SEED {run.provenance?.seed_offset ?? '—'} · ENGINE {run.provenance?.engine_sha256?.slice(0, 10) ?? '—'} · POLICY {Object.entries(run.provenance?.policy_sha256_by_file || {}).map(([path, hash]) => `${path.includes('mccfr') ? 'MCCFR' : path.includes('_v2') ? 'V2' : 'V1'} ${hash.slice(0, 10)}`).join(' · ') || run.provenance?.policy_sha256?.slice(0, 10) || '—'}</small>{Object.entries(run.results).filter(([name]) => !(run.warning && name.includes('adaptive'))).map(([name, result]) => <div className="result-row" key={name}><span>{name.replaceAll('_', ' ')}</span><b>{pct(result.win_rate)}</b></div>)}</div>)}</details></aside></div></section> : <section className="info-page system-page"><div className="page-intro"><div><p className="eyebrow">GAME SYSTEM</p><h1>Table status.</h1><p>Play in your browser. The game engine validates every move and saves each match for its final replay.</p></div></div><div className="system-grid"><div><span>CONNECTION</span><strong>{health?.ok ? 'Online' : health === null ? 'Checking' : 'Offline'}</strong></div><div><span>TRAINED POLICY</span><strong>{health?.policy_ok ? 'Checksum verified' : health === null ? 'Checking' : 'Unavailable'}</strong></div><div><span>RULESET</span><strong>Five dice · first to five</strong></div><div><span>COMPLETED MATCHES</span><strong>{leaderboard?.completed_matches ?? '—'}</strong></div><div><span>HUMAN / AI WINS</span><strong>{leaderboard ? `${leaderboard.human_wins} / ${leaderboard.ai_wins}` : '—'}</strong></div></div>{game && <button className="secondary-action" onClick={deleteMatch}>Delete this visitor match</button>}</section>}

    {error && <div className="error-toast" role="alert">{error}</div>}
    {tutorial && <div className="tutorial-backdrop" role="dialog" aria-modal="true" aria-label="How to play"><div className="tutorial"><button className="close" aria-label="Close tutorial" onClick={() => setTutorial(false)}>×</button><span className="eyebrow">RULE {tutorialStep + 1} OF 3</span><h2>{['Five dice each', 'Raise the quantity', 'Challenge for a point'][tutorialStep]}</h2><p>{['You see your five dice. The AI sees only its five. Both hands are revealed after a challenge.', 'A bid says how many of all ten dice show one face. A new bid must claim more dice; the face can change.', 'Challenge a claim you think is false. The round winner gets one point. First to five wins.'][tutorialStep]}</p><button className="primary-action" onClick={() => tutorialStep < 2 ? setTutorialStep(tutorialStep + 1) : setTutorial(false)}>{tutorialStep < 2 ? 'Next rule' : 'Start playing'} <span aria-hidden="true">→</span></button></div></div>}
    <footer><span>BLUFF.EXE</span><span>FIVE DICE / NO WILDS / FIRST TO FIVE</span><span>EXHIBITION BUILD</span></footer>
  </main>;
}
