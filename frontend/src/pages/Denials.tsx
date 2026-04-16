import { useQuery, useMutation } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer, Legend } from 'recharts';
import { api } from '../api/client';

const COLORS = ['#2E75B6', '#f97316', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#14b8a6', '#64748b'];

export default function Denials() {
  const { data, refetch } = useQuery({
    queryKey: ['denials'],
    queryFn: () => api<any>('/denials?page_size=50'),
  });
  const { data: summary } = useQuery({
    queryKey: ['denials-summary'],
    queryFn: () => api<any>('/denials/summary'),
  });

  const runBatch = useMutation({
    mutationFn: async () => {
      const pending = data?.items?.filter((d: any) => !d.appeal_submitted_at).slice(0, 3) || [];
      for (const d of pending) {
        await api('/agents/denial/run', { method: 'POST', body: JSON.stringify({ denial_id: d.denial_id }) });
      }
      return pending.length;
    },
    onSuccess: () => setTimeout(refetch, 2000),
  });

  return (
    <div className="p-6 space-y-4">
      <div className="flex justify-between items-center">
        <h1 className="text-2xl font-semibold">Denials</h1>
        <button
          className="px-3 py-1.5 bg-rose-600 text-white text-sm rounded hover:bg-rose-700"
          onClick={() => runBatch.mutate()}
          disabled={runBatch.isPending}
        >
          Run Denial Agent (batch)
        </button>
      </div>

      <div className="grid grid-cols-3 gap-4">
        <div className="bg-white p-4 rounded border border-slate-200">
          <div className="font-semibold mb-2">Root Cause Breakdown</div>
          <div className="h-52">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={summary?.by_category || []}
                  dataKey="count"
                  nameKey="category"
                  outerRadius={70}
                  label
                >
                  {(summary?.by_category || []).map((_: any, i: number) => (
                    <Cell key={i} fill={COLORS[i % COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip />
                <Legend verticalAlign="bottom" height={36} />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="col-span-2 bg-white p-4 rounded border border-slate-200">
          <div className="font-semibold mb-2">Denial Queue</div>
          <div className="text-xs text-slate-500 mb-2">{data?.total ?? 0} denials</div>
          <div className="overflow-auto max-h-80">
            <table className="w-full text-sm">
              <thead className="bg-slate-50"><tr>
                <th className="text-left px-2 py-1">ID</th>
                <th className="text-left px-2 py-1">Claim</th>
                <th className="text-left px-2 py-1">CARC</th>
                <th className="text-left px-2 py-1">Category</th>
                <th className="text-left px-2 py-1">Appeal Deadline</th>
                <th className="text-left px-2 py-1">Submitted</th>
              </tr></thead>
              <tbody>
                {data?.items?.map((d: any) => (
                  <tr key={d.denial_id} className="border-t">
                    <td className="px-2 py-1 font-mono text-xs">{d.denial_id}</td>
                    <td className="px-2 py-1 font-mono text-xs">
                      <Link to={`/claims/${d.claim_id}`} className="text-envblue hover:underline">
                        {d.claim_id}
                      </Link>
                    </td>
                    <td className="px-2 py-1">{d.carc_code}</td>
                    <td className="px-2 py-1">{d.denial_category}</td>
                    <td className="px-2 py-1">{d.appeal_deadline}</td>
                    <td className="px-2 py-1">{d.appeal_submitted_at ? '✓' : '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
}
