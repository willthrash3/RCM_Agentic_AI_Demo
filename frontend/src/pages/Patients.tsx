import { useState } from 'react';
import { useQuery, useMutation } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { api } from '../api/client';

export default function Patients() {
  const [search, setSearch] = useState('');
  const runCollections = useMutation({
    mutationFn: () => api<any>('/agents/collections/run', { method: 'POST', body: '{}' }),
  });
  const { data } = useQuery({
    queryKey: ['patients', search],
    queryFn: () => {
      const q = new URLSearchParams({ page_size: '50' });
      if (search) q.set('search', search);
      return api<any>(`/patients?${q}`);
    },
  });

  return (
    <div className="p-6 space-y-4">
      <div className="flex justify-between items-center">
        <h1 className="text-2xl font-semibold">Patients</h1>
        <button
          className="px-3 py-1.5 bg-teal-600 text-white text-sm rounded hover:bg-teal-700"
          type="button"
          onClick={() => runCollections.mutate()}
          disabled={runCollections.isPending}
        >
          {runCollections.isPending ? 'Running…' : 'Run Collections'}
        </button>
      </div>

      <input
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        placeholder="Search by name or MRN…"
        className="border rounded px-3 py-1.5 text-sm w-72"
      />
      <div className="text-xs text-slate-500">{data?.total ?? 0} patients</div>

      <div className="bg-white rounded-lg border border-slate-200 overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-slate-50"><tr>
            <th className="text-left px-3 py-2">ID</th>
            <th className="text-left px-3 py-2">Name</th>
            <th className="text-left px-3 py-2">MRN</th>
            <th className="text-left px-3 py-2">DOB</th>
            <th className="text-left px-3 py-2">Primary Payer</th>
            <th className="text-right px-3 py-2">Propensity</th>
            <th className="text-left px-3 py-2">Location</th>
          </tr></thead>
          <tbody>
            {data?.items?.map((p: any) => (
              <tr key={p.patient_id} className="border-t hover:bg-slate-50">
                <td className="px-3 py-2 font-mono">
                  <Link to={`/patients/${p.patient_id}`} className="text-envblue hover:underline">
                    {p.patient_id}
                  </Link>
                </td>
                <td className="px-3 py-2">{p.first_name} {p.last_name}</td>
                <td className="px-3 py-2 font-mono text-xs">{p.mrn}</td>
                <td className="px-3 py-2">{p.dob}</td>
                <td className="px-3 py-2">{p.primary_payer_id}</td>
                <td className="px-3 py-2 text-right">{Number(p.propensity_score).toFixed(2)}</td>
                <td className="px-3 py-2">{p.city}, {p.state}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
