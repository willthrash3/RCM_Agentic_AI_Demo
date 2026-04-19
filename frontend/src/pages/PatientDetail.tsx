import { useQuery, useMutation } from '@tanstack/react-query';
import { useParams, Link } from 'react-router-dom';
import { api } from '../api/client';

export default function PatientDetail() {
  const { patientId } = useParams();
  const { data, refetch } = useQuery({
    queryKey: ['patient', patientId],
    queryFn: () => api<any>(`/patients/${patientId}`),
    enabled: !!patientId,
  });

  const runEligibility = useMutation({
    mutationFn: () => api<any>('/agents/eligibility/run', {
      method: 'POST',
      body: JSON.stringify({
        patient_id: patientId,
        service_date: new Date().toISOString().slice(0, 10),
      }),
    }),
    onSuccess: () => setTimeout(() => refetch(), 1500),
  });

  const runCollections = useMutation({
    mutationFn: () => api<any>('/agents/collections/run', { method: 'POST', body: '{}' }),
    onSuccess: () => setTimeout(() => refetch(), 1500),
  });

  if (!data) return <div className="p-6">Loading…</div>;
  return (
    <div className="p-6 space-y-4">
      <div className="flex justify-between items-center">
        <h1 className="text-2xl font-semibold">
          {data.first_name} {data.last_name}{' '}
          <span className="text-slate-500 text-lg font-normal">{data.mrn}</span>
        </h1>
        <div className="flex gap-2">
          <button
            className="px-3 py-1.5 bg-envblue text-white text-sm rounded hover:bg-blue-700"
            onClick={() => runEligibility.mutate()}
            disabled={runEligibility.isPending}
          >
            Run Eligibility Check
          </button>
          <button
            className="px-3 py-1.5 bg-teal-600 text-white text-sm rounded hover:bg-teal-700"
            onClick={() => runCollections.mutate()}
            disabled={runCollections.isPending}
          >
            Run Collections Agent
          </button>
        </div>
      </div>

      <div className="grid grid-cols-3 gap-4 text-sm">
        <div className="bg-white p-4 rounded border border-slate-200">
          <div className="font-semibold mb-1">Demographics</div>
          <div>DOB: {data.dob}</div>
          <div>Gender: {data.gender}</div>
          <div>{data.address_line1}</div>
          <div>{data.city}, {data.state} {data.zip_code}</div>
          <div className="mt-2">Phone: {data.phone}</div>
          <div>Email: {data.email}</div>
          <div>Language: {data.language_pref}</div>
        </div>

        <div className="bg-white p-4 rounded border border-slate-200">
          <div className="font-semibold mb-1">Insurance</div>
          <div>Primary: {data.primary_payer_id}</div>
          <div>Secondary: {data.secondary_payer_id || '—'}</div>
          <div className="mt-2 font-semibold">Recent Eligibility</div>
          {data.recent_eligibility?.length === 0 && <div className="text-xs text-slate-500">No recent checks</div>}
          {data.recent_eligibility?.map((e: any) => (
            <div key={e.eligibility_id} className="text-xs mt-1">
              {e.payer_id} · {e.plan_type} ·{' '}
              <span className={e.in_network ? 'text-emerald-700' : 'text-rose-700'}>
                {e.in_network ? 'in-network' : 'out-of-network'}
              </span>
            </div>
          ))}
        </div>

        <div className="bg-white p-4 rounded border border-slate-200">
          <div className="font-semibold mb-1">Balance</div>
          <div className="text-3xl font-bold">${data.balance_due.toFixed(2)}</div>
          <div className="text-xs text-slate-500 mt-2">Propensity score: {data.propensity_score}</div>
        </div>
      </div>

      <div className="bg-white rounded-lg border border-slate-200 overflow-hidden">
        <div className="px-4 py-2 border-b font-semibold">Encounter Timeline</div>
        <table className="w-full text-sm">
          <thead className="bg-slate-50"><tr>
            <th className="text-left px-3 py-2">Date</th>
            <th className="text-left px-3 py-2">Type</th>
            <th className="text-left px-3 py-2">Status</th>
            <th className="text-left px-3 py-2">Scenario</th>
            <th className="text-left px-3 py-2">Encounter ID</th>
          </tr></thead>
          <tbody>
            {data.encounters?.map((e: any) => (
              <tr key={e.encounter_id} className="border-t">
                <td className="px-3 py-2">{e.service_date}</td>
                <td className="px-3 py-2">{e.encounter_type}</td>
                <td className="px-3 py-2">{e.status}</td>
                <td className="px-3 py-2 text-xs">{e.scenario_id}</td>
                <td className="px-3 py-2 font-mono text-xs">{e.encounter_id}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
