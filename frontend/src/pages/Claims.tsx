import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import clsx from 'clsx';
import { api } from '../api/client';

interface Claim {
  claim_id: string;
  encounter_id: string;
  payer_id: string;
  total_billed: number;
  total_paid: number;
  claim_status: string;
  submission_date: string;
  rejection_reason: string | null;
  scrub_score: number | null;
}

const statusColor: Record<string, string> = {
  Paid: 'bg-emerald-100 text-emerald-800',
  Submitted: 'bg-sky-100 text-sky-800',
  Denied: 'bg-rose-100 text-rose-800',
  Appealed: 'bg-violet-100 text-violet-800',
  Draft: 'bg-slate-100 text-slate-700',
};

function scrubChip(score: number | null) {
  if (score === null) return null;
  const color =
    score >= 0.90 ? 'bg-emerald-100 text-emerald-800'
    : score >= 0.75 ? 'bg-amber-100 text-amber-800'
    : 'bg-rose-100 text-rose-800';
  return <span className={clsx('text-xs px-2 py-0.5 rounded', color)}>{score.toFixed(2)}</span>;
}

export default function Claims() {
  const [status, setStatus] = useState('');
  const [payerId, setPayerId] = useState('');
  const { data } = useQuery({
    queryKey: ['claims', status, payerId],
    queryFn: () => {
      const q = new URLSearchParams();
      if (status) q.set('status', status);
      if (payerId) q.set('payer_id', payerId);
      q.set('page_size', '50');
      return api<{ items: Claim[]; total: number }>(`/claims?${q}`);
    },
  });

  return (
    <div className="p-6 space-y-4">
      <h1 className="text-2xl font-semibold">Claims</h1>

      <div className="flex gap-2 text-sm">
        <select
          value={status}
          onChange={(e) => setStatus(e.target.value)}
          className="border rounded px-2 py-1"
        >
          <option value="">All statuses</option>
          {['Draft', 'Submitted', 'Paid', 'Denied', 'Appealed'].map((s) => (
            <option key={s} value={s}>{s}</option>
          ))}
        </select>
        <select
          value={payerId}
          onChange={(e) => setPayerId(e.target.value)}
          className="border rounded px-2 py-1"
        >
          <option value="">All payers</option>
          {['payer-001','payer-002','payer-003','payer-004','payer-005','payer-006','payer-007'].map((p) => (
            <option key={p} value={p}>{p}</option>
          ))}
        </select>
      </div>

      <div className="text-xs text-slate-500">{data?.total ?? 0} claims</div>

      <div className="bg-white rounded-lg shadow-sm border border-slate-200 overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 text-slate-600">
            <tr>
              <th className="text-left px-3 py-2">Claim</th>
              <th className="text-left px-3 py-2">Payer</th>
              <th className="text-right px-3 py-2">Billed</th>
              <th className="text-right px-3 py-2">Paid</th>
              <th className="text-left px-3 py-2">Status</th>
              <th className="text-left px-3 py-2">Scrub</th>
              <th className="text-left px-3 py-2">CARC</th>
              <th className="text-left px-3 py-2">Submitted</th>
            </tr>
          </thead>
          <tbody>
            {data?.items.map((c) => (
              <tr key={c.claim_id} className="border-t hover:bg-slate-50">
                <td className="px-3 py-2 font-mono">
                  <Link to={`/claims/${c.claim_id}`} className="text-envblue hover:underline">
                    {c.claim_id}
                  </Link>
                </td>
                <td className="px-3 py-2">{c.payer_id}</td>
                <td className="px-3 py-2 text-right">${Number(c.total_billed).toFixed(2)}</td>
                <td className="px-3 py-2 text-right">${Number(c.total_paid || 0).toFixed(2)}</td>
                <td className="px-3 py-2">
                  <span className={clsx('text-xs px-2 py-0.5 rounded', statusColor[c.claim_status])}>
                    {c.claim_status}
                  </span>
                </td>
                <td className="px-3 py-2">{scrubChip(c.scrub_score)}</td>
                <td className="px-3 py-2 text-xs">{c.rejection_reason || '—'}</td>
                <td className="px-3 py-2 text-xs">{c.submission_date || '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
