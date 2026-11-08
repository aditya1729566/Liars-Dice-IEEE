'use client';

const pipCells: Record<number, number[]> = {
  1: [5],
  2: [1, 9],
  3: [1, 5, 9],
  4: [1, 3, 7, 9],
  5: [1, 3, 5, 7, 9],
  6: [1, 3, 4, 6, 7, 9],
};

export function Die({ value, concealed = false, small = false }: { value?: number; concealed?: boolean; small?: boolean }) {
  return <span className={`die${concealed ? ' die-back' : ''}${small ? ' die-small' : ''}`} role="img" aria-label={concealed ? 'Concealed die' : `Die showing ${value}`}>
    {concealed ? <span className="die-back-mark" aria-hidden="true">?</span> : <span className="pip-grid" aria-hidden="true">{Array.from({ length: 9 }, (_, index) => <i key={index} className={pipCells[value ?? 1].includes(index + 1) ? 'pip on' : 'pip'} />)}</span>}
  </span>;
}

export default function DiceTable({ hand, aiHand, bid, round }: { hand: number[]; aiHand?: number[] | null; bid?: { q: number; f: number } | null; round?: number }) {
  return <div className="dice-table">
    <div className="table-hand table-hand-ai">
      <div className="table-side-name"><span>AI HAND</span><small>{aiHand ? 'REVEALED' : 'HIDDEN UNTIL CHALLENGE'}</small></div>
      <div className="dice-row" aria-label={aiHand ? `AI dice: ${aiHand.join(', ')}` : 'Five AI dice concealed'}>{Array.from({ length: 5 }, (_, i) => <Die key={i} value={aiHand?.[i]} concealed={!aiHand} />)}</div>
    </div>
    <div className="table-center">
      <span className="table-rule">ROUND {round ? String(round).padStart(2, '0') : '—'} <span aria-hidden="true">/</span> CURRENT CLAIM</span>
      {bid ? <div className="claim-graphic"><strong>{String(bid.q).padStart(2, '0')}</strong><span>dice showing</span><Die value={bid.f} small /></div> : <div className="claim-empty">No claim yet</div>}
      <p>Only the quantity must increase. Any face can follow.</p>
    </div>
    <div className="table-hand table-hand-you">
      <div className="table-side-name"><span>YOUR HAND</span><small>ONLY YOU CAN SEE THIS</small></div>
      <div className="dice-row" aria-label={`Your dice: ${hand.join(', ')}`}>{hand.map((value, i) => <Die key={i} value={value} />)}</div>
    </div>
  </div>;
}
