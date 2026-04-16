import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useParams } from 'react-router-dom';
import { api } from '../api/client';

export default function ClaimDetail() {
  const { claimId } = useParams();
  const qc = useQueryClient();
  const { data } = useQuery({
    queryKey: ['claim', claimId],
    queryFn: () => api<any>(`/claims/${claimId}`),
    enabled: !!claimId,
  });

  const runScrub = useMutation({
    mutationFn: () => api<any>('/agents/scrubbing/run', {
      method: 'POST', body: JSON.stringify({ claim_id: claimId }),
    }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['claim', claimId] }),
  });

  const runDenial = useMutation({
    mutationFn: () => api<any>('/agents/denial/run', {
      method: 'POST', body: JSON.stringify({ denial_id: data?.denial?.denial_id }),
    }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['claim', claimId] }),
  });

  if (!data) return <div className="p-6">Loading…</div>;
  return (
    <div className="p-6 space-y-4">
      <div className="flex justify-between items-center">
        <h1 className="text-2xl font-semibold">Claim {data.claim_id}</h1>
        <div className="flex gap-2">
          <button
            className="px-3 py-1.5 bg-envblue text-white text-sm rounded hover:bg-blue-700"
            onClick={() => runScrub.mutate()}
            disabled={runScrub.isPending}
          >
            Run Scrub Agent
          </button>
          {data.denial && (
            <button
              className="px-3 py-1.5 bg-rose-600 text-white text-sm rounded hover:bg-rose-700"
              onClick={() => runDenial.mutate()}
              disabled={runDenial.isPending}
            >
              Run Denial Agent
            </button>
          )}
        </div>
      </div>

      <div className="grid grid-cols-3 gap-4">
        <div className="bg-white p-4 rounded-lg border border-slate-200">
          <div className="text-xs text-slate-500">Payer</div>
          <div className="font-semibold">{data.payer_id}</div>
          <div className="text-xs text-slate-500 mt-3">Status</div>
          <div className="font-semibold">{data.claim_status}</div>
        </div>
        <div className="bg-white p-4 rounded-lg border border-slate-200">
          <div className="text-xs text-slate-500">Billed</div>
          <div className="font-semibold">${Number(data.total_billed).toFixed(2)}</div>
          <div className="text-xs text-slate-500 mt-3">Paid</div>
          <div className="font-semibold">${Number(data.total_paid || 0).toFixed(2)}</div>
        </div>
        <div className="bg-white p-4 rounded-lg border border-slate-200">
          <div className="text-xs text-slate-500">Scrub Score</div>
          <div className="font-semibold">{data.scrub_score ?? '—'}</div>
          <div className="text-xs text-slate-500 mt-3">Timely Filing Deadline</div>
          <div className="font-semibold">{data.timely_filing_deadline || '—'}</div>
        </div>
      </div>

      <div className="bg-white rounded-lg border border-slate-200 overflow-hidden">
        <div className="px-4 py-2 border-b font-semibold">Line Items</div>
        <table className="w-full text-sm">
          <thead className="bg-slate-50"><tr>
            <th className="text-left px-3 py-2">CPT</th>
            <th className="text-left px-3 py-2">ICD-10</th>
            <th className="text-left px-3 py-2">Modifier</th>
            <th className="text-right px-3 py-2">Units</th>
            <th className="text-right px-3 py-2">Charge</th>
            <th className="text-right px-3 py-2">Allowed</th>
            <th className="text-right px-3 py-2">Conf.</th>
          </tr></thead>
          <tbody>
            {data.lines?.map((l: any) => (
              <tr key={l.line_id} className="border-t">
                <td className="px-3 py-2 font-mono">{l.cpt_code}</td>
                <td className="px-3 py-2 font-mono">{l.icd10_primary}{l.icd10_secondary ? ` / ${l.icd10_secondary}` : ''}</td>
                <td className="px-3 py-2">{l.modifier || '—'}</td>
                <td className="px-3 py-2 text-right">{l.units}</td>
                <td className="px-3 py-2 text-right">${Number(l.charge_amount).toFixed(2)}</td>
                <td className="px-3 py-2 text-right">${Number(l.allowed_amount || 0).toFixed(2)}</td>
                <td className="px-3 py-2 text-right">{l.coding_confidence ?? '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {data.denial && (
        <div className="bg-white rounded-lg border border-slate-200 p-4">
          <div className="font-semibold mb-2">Denial</div>
          <div className="grid grid-cols-2 gap-3 text-sm">
            <div><span className="text-slate-500">Category: </span>{data.denial.denial_category}</div>
            <div><span className="text-slate-500">CARC: </span>{data.denial.carc_code}</div>
            <div><span className="text-slate-500">Denied: </span>{data.denial.denial_date}</div>
            <div><span className="text-slate-500">Appeal deadline: </span>{data.denial.appeal_deadline}</div>
          </div>
          {data.denial.appeal_letter_text && (
            <details className="mt-3">
              <summary className="cursor-pointer text-envblue">Appeal letter</summary>
              <pre className="whitespace-pre-wrap text-xs mt-2 p-3 bg-slate-50 rounded border">
                {data.denial.appeal_letter_text}
              </pre>
            </details>
          )}
        </div>
      )}

      <div className="bg-white rounded-lg border border-slate-200 p-4">
        <div className="font-semibold mb-2">Agent Event Timeline</div>
        <div className="space-y-1 text-xs font-mono max-h-80 overflow-auto">
          {data.events?.map((ev: any) => (
            <div key={ev.event_id} className="p-2 border rounded flex justify-between">
              <div>
                <span className="font-semibold">{ev.agent_name}</span> · {ev.action_type}
                {ev.reasoning_trace && <div className="text-slate-600 whitespace-pre-wrap mt-1">{ev.reasoning_trace}</div>}
              </div>
              <div className="text-[10px] text-slate-500">{new Date(ev.created_at).toLocaleString()}</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
