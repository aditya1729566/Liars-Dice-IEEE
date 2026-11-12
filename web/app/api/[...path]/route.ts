import { execFileSync } from 'node:child_process';
import { createHash, randomBytes } from 'node:crypto';
import { existsSync, readFileSync } from 'node:fs';
import { join } from 'node:path';
import { BlobPreconditionFailedError, del, get, head, list, put } from '@vercel/blob';
import { buildReplay, truthPrior, type ReplayState } from '../../../lib/replay';

export const dynamic = 'force-dynamic';
export const runtime = 'nodejs';
const root = join(process.cwd(), 'runtime');
const ruleset = 'fixed5_score5_quantity_only_v1';
const agents = new Set(['random', 'probability', 'aggressive', 'cfr2', 'adaptive', 'mccfr_external_v1', 'mccfr_external_v2', 'rebel_transfer_v1']);
type State = ReplayState & { ruleset: string; agent: string; version: number; phase: string; hands: number[][] };
type StoredMatch = { state: State; created: number; requests: Record<string, object> };
type EngineResult = { state?: State; view?: Record<string, unknown>; probability?: number; error?: string };
class ApiError extends Error { constructor(message: string, readonly status = 400) { super(message); } }

function engine(command: object): EngineResult {
  try {
    const raw = execFileSync(join(root, 'bluff_engine'), { cwd: root, input: JSON.stringify(command), encoding: 'utf8', timeout: 5000, maxBuffer: 8 * 1024 * 1024 });
    const result = JSON.parse(raw) as EngineResult;
    if (result.error) throw new ApiError(result.error);
    return result;
  } catch (error) {
    if (error instanceof ApiError) throw error;
    const output = error instanceof Error && 'stdout' in error ? String(error.stdout) : '';
    try { const parsed = JSON.parse(output); if (parsed.error) throw new ApiError(parsed.error); } catch (parseError) { if (parseError instanceof ApiError) throw parseError; }
    throw new Error('game engine failed');
  }
}
function policyOk(ids = ['fixed5_cfr_100k', 'fixed5_cfr_v2_100k']): boolean {
  try {
    const entries = JSON.parse(readFileSync(join(root, 'policies/index.json'), 'utf8')).policies as { id: string; policy_path: string; policy_sha256: string }[];
    return ids.every(id => {
      const entry = entries.find(item => item.id === id);
      if (!entry) return false;
      const data = readFileSync(join(root, entry.policy_path));
      return createHash('sha256').update(data).digest('hex') === entry.policy_sha256;
    });
  } catch { return false; }
}
function pathFor(id: string) { if (!/^[A-Za-z0-9_-]{20,40}$/.test(id)) throw new ApiError('match not found', 404); return `matches/${id}.json`; }
async function readMatch(id: string): Promise<{ match: StoredMatch; etag: string }> {
  const result = await get(pathFor(id), { access: 'private', useCache: false });
  if (!result || result.statusCode !== 200 || !result.stream) throw new ApiError('match not found', 404);
  const match = JSON.parse(await new Response(result.stream).text()) as StoredMatch;
  if (match.state.ruleset !== ruleset) throw new ApiError('legacy match uses an obsolete ruleset', 404);
  const metadata = await head(pathFor(id));
  if (metadata.etag !== result.blob.etag.replace(/^W\//, '')) throw new ApiError('concurrent update; retry the action', 409);
  return { match, etag: metadata.etag };
}
function response(id: string, match: StoredMatch, view: Record<string, unknown>) {
  return { id, duration_seconds: Math.max(0, Math.floor((Date.now() - match.created) / 1000)), ...view };
}
function safeJson(value: object, status = 200) { return Response.json(value, { status, headers: { 'Cache-Control': 'no-store' } }); }
async function body(request: Request): Promise<Record<string, unknown>> {
  if (Number(request.headers.get('content-length') || 0) > 16384) throw new ApiError('request too large');
  const raw = await request.text();
  if (raw.length > 16384) throw new ApiError('request too large');
  try { const value = JSON.parse(raw || '{}'); if (!value || typeof value !== 'object' || Array.isArray(value)) throw Error(); return value; }
  catch { throw new ApiError('invalid JSON body'); }
}
async function leaderboard() {
  const counts = { completed_matches: 0, human_wins: 0, ai_wins: 0 };
  let cursor: string | undefined;
  do {
    const page = await list({ prefix: 'completed/', cursor, limit: 1000 });
    for (const item of page.blobs) {
      counts.completed_matches++;
      if (item.pathname.startsWith('completed/HUMAN/')) counts.human_wins++;
      if (item.pathname.startsWith('completed/AI/')) counts.ai_wins++;
    }
    cursor = page.hasMore ? page.cursor : undefined;
  } while (cursor);
  return counts;
}
async function dispatch(method: string, request: Request, bits: string[]): Promise<object> {
  if (method === 'GET' && bits.join('/') === 'health') {
    const ok = existsSync(join(root, 'bluff_engine')) && policyOk() && Boolean(process.env.BLOB_READ_WRITE_TOKEN);
    return { ok, engine: 'bluff_engine', ruleset, policy_ok: policyOk() };
  }
  if (method === 'GET' && bits.join('/') === 'rules') return { version: ruleset, faces: 6, wild: false, dice_per_player: 5, target_score: 5, bid_order: 'quantity only', next_starter: 'round loser' };
  if (method === 'GET' && bits.join('/') === 'agents') {
    const versions: Record<string, string> = { cfr2: 'fixed5_cfr_v2_100k', adaptive: 'fixed5_cfr_100k', mccfr_external_v1: 'mccfr_external_v1', mccfr_external_v2: 'mccfr_external_v2', rebel_transfer_v1: 'rebel_transfer_v1' };
    return { agents: [...agents].sort().map(id => ({ id, policy_version: versions[id] || 'fixed5_heuristic_v1', available: id === 'rebel_transfer_v1' ? false : versions[id] ? policyOk(id.startsWith('mccfr_external_') ? [id] : id === 'cfr2' ? ['fixed5_cfr_v2_100k'] : ['fixed5_cfr_100k']) : true, trained: id === 'cfr2' || id.startsWith('mccfr_external_') || id === 'rebel_transfer_v1', uses_trained_base: id === 'adaptive', scope: id === 'rebel_transfer_v1' ? 'local PyTorch transfer model; unavailable in this deployment' : id === 'mccfr_external_v2' ? 'external-sampling MCCFR with wider bids and depth-limited match utility' : id === 'mccfr_external_v1' ? 'external-sampling MCCFR one-round imperfect-recall abstraction' : id === 'cfr2' ? 'wider imperfect-recall one-round CFR abstraction' : id === 'adaptive' ? 'public-outcome model plus original CFR base' : 'heuristic' })) };
  }
  if (method === 'GET' && bits.join('/') === 'research/summary') {
    const runs = JSON.parse(readFileSync(join(root, 'docs/research_runs.json'), 'utf8')) as object[];
    return { status: runs.length ? 'completed' : 'no completed evaluation', runs };
  }
  if (method === 'GET' && bits.join('/') === 'leaderboard') return leaderboard();
  if (method === 'POST' && bits.join('/') === 'matches') {
    const input = await body(request);
    const agent = input.agent ?? 'probability';
    if (input.n !== 5 || typeof agent !== 'string' || !agents.has(agent)) throw new ApiError('this game requires five dice and a supported agent');
    if (agent === 'rebel_transfer_v1') throw new ApiError('ReBeL requires the local PyTorch runtime; use make setup-rebel and make dev');
    if (['cfr2', 'adaptive', 'mccfr_external_v1', 'mccfr_external_v2'].includes(agent) && !policyOk(agent.startsWith('mccfr_external_') ? [agent] : agent === 'cfr2' ? ['fixed5_cfr_v2_100k'] : ['fixed5_cfr_100k'])) throw new ApiError('trained policy checksum failed');
    const result = engine({ op: 'new', n: 5, agent });
    if (!result.state || !result.view) throw Error('engine returned incomplete match');
    const id = randomBytes(18).toString('base64url');
    const match: StoredMatch = { state: result.state, created: Date.now(), requests: {} };
    await put(pathFor(id), JSON.stringify(match), { access: 'private', contentType: 'application/json' });
    return response(id, match, result.view);
  }
  if (bits[0] !== 'matches' || !bits[1]) throw new ApiError('endpoint not found', 404);
  const id = bits[1];
  if (method === 'DELETE' && bits.length === 2) {
    const { match } = await readMatch(id);
    await del(pathFor(id));
    if (match.state.status === 'COMPLETED' && match.state.winner) await del(`completed/${match.state.winner}/${id}.json`);
    return { deleted: true };
  }
  if (method === 'GET') {
    const { match } = await readMatch(id);
    const state = match.state;
    const view = engine({ op: 'view', state }).view;
    if (!view) throw Error('engine returned no view');
    if (bits.length === 2) return response(id, match, view);
    if (bits[2] === 'events' && bits.length === 3) return { events: view.events };
    if (bits[2] === 'research' && bits.length === 3) {
      if (state.status !== 'COMPLETED') throw new ApiError('match research is available after the final score', 409);
      return { id, agent: state.agent, winner: state.winner, scores: state.scores, rounds: state.round, decisions: state.ai_decisions || [], reveals: state.events.filter(e => e.type === 'reveal'), replay: buildReplay(state), method: "Replay slides reconstruct authoritative events and post-match hands. AI move weights and sources come from recorded decisions. The AI's read of human moves is a deterministic hypothesis from its own hand and public actions, not a stored CFR thought or knowledge of human intent. Truth probabilities are binomial priors over five unseen dice, not strategic posteriors." };
    }
    if (bits[2] === 'analysis' && bits.length === 4) {
      const round = Number(bits[3]);
      const reveal = [...state.events].reverse().find(e => e.type === 'reveal' && e.round === round);
      if (!reveal?.bid || !reveal.hands) throw new ApiError('round not revealed', 404);
      return { round, bid: reveal.bid, actual: reveal.actual, true: reveal.true, loser: reveal.winner === 'HUMAN' ? 'AI' : 'HUMAN', naive_prior_from_ai_hand: truthPrior(reveal.bid.q, reveal.bid.f, reveal.hands[1], reveal.hands[0].length), policy: state.agent, note: 'Prior before strategic bid evidence; no posterior or action propensity is claimed.' };
    }
  }
  if (method === 'POST' && bits.length === 3 && ['actions', 'next-round'].includes(bits[2])) {
    const input = await body(request);
    const key = String(input.idempotency_key ?? '');
    for (let attempt = 0; attempt < 4; attempt++) {
      const { match, etag } = await readMatch(id);
      if (match.requests[key]) return match.requests[key];
      if (key.length < 8 || key.length > 128) throw new ApiError('idempotency_key must be 8–128 characters');
      if (input.expected_version !== match.state.version) throw new ApiError('stale match version', 409);
      const command = bits[2] === 'actions' ? { op: 'act', state: match.state, action: input.action } : { op: 'next_round', state: match.state };
      const result = engine(command);
      if (!result.state || !result.view) throw Error('engine returned incomplete result');
      const next: StoredMatch = { ...match, state: result.state, requests: { ...match.requests } };
      const outgoing = response(id, next, result.view);
      next.requests[key] = outgoing;
      try {
        await put(pathFor(id), JSON.stringify(next), { access: 'private', contentType: 'application/json', allowOverwrite: true, ifMatch: etag });
        if (result.state.status === 'COMPLETED' && result.state.winner) await put(`completed/${result.state.winner}/${id}.json`, '{}', { access: 'private', contentType: 'application/json' });
        return outgoing;
      } catch (error) {
        if (!(error instanceof BlobPreconditionFailedError)) throw error;
        console.error('match write conflict', { attempt, etag, message: error.message });
      }
    }
    throw new ApiError('concurrent update; retry the action', 409);
  }
  throw new ApiError('endpoint not found', 404);
}
async function handle(request: Request, method: string) {
  const pathname = new URL(request.url).pathname;
  if (!process.env.BLOB_READ_WRITE_TOKEN) {
    try {
      const target = new URL(pathname + new URL(request.url).search, 'http://127.0.0.1:8787');
      const upstream = await fetch(target, { method, headers: { 'Content-Type': request.headers.get('Content-Type') || 'application/json' }, body: ['POST', 'PUT', 'PATCH'].includes(method) ? await request.text() : undefined, cache: 'no-store' });
      return new Response(upstream.body, { status: upstream.status, headers: { 'Content-Type': upstream.headers.get('Content-Type') || 'application/json', 'Cache-Control': 'no-store' } });
    } catch { return safeJson({ error: 'local game API is offline' }, 503); }
  }
  try {
    if (request.headers.get('Origin') && new URL(request.headers.get('Origin')!).origin !== new URL(request.url).origin) throw new ApiError('origin not allowed', 403);
    const bits = pathname.split('/').filter(Boolean).slice(1);
    return safeJson(await dispatch(method, request, bits), method === 'POST' ? 201 : 200);
  } catch (error) {
    if (error instanceof ApiError) return safeJson({ error: error.message }, error.status);
    console.error('BLUFF API failed', error);
    return safeJson({ error: 'internal game error' }, 500);
  }
}
export async function GET(request: Request) { return handle(request, 'GET'); }
export async function POST(request: Request) { return handle(request, 'POST'); }
export async function DELETE(request: Request) { return handle(request, 'DELETE'); }
