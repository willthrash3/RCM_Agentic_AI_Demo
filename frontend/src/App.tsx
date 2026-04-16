import { Routes, Route, Navigate } from 'react-router-dom';
import Layout from './components/Layout';
import Dashboard from './pages/Dashboard';
import Claims from './pages/Claims';
import ClaimDetail from './pages/ClaimDetail';
import Patients from './pages/Patients';
import PatientDetail from './pages/PatientDetail';
import ReviewQueue from './pages/ReviewQueue';
import Denials from './pages/Denials';
import AgentTrace from './pages/AgentTrace';
import Analytics from './pages/Analytics';
import Scenarios from './pages/Scenarios';

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Layout />}>
        <Route index element={<Navigate to="/dashboard" replace />} />
        <Route path="dashboard" element={<Dashboard />} />
        <Route path="claims" element={<Claims />} />
        <Route path="claims/:claimId" element={<ClaimDetail />} />
        <Route path="patients" element={<Patients />} />
        <Route path="patients/:patientId" element={<PatientDetail />} />
        <Route path="review-queue" element={<ReviewQueue />} />
        <Route path="denials" element={<Denials />} />
        <Route path="agent-trace" element={<AgentTrace />} />
        <Route path="analytics" element={<Analytics />} />
        <Route path="scenarios" element={<Scenarios />} />
      </Route>
    </Routes>
  );
}
