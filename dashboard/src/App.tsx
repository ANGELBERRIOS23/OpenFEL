import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { hasKey } from './lib/api';
import { applyTheme } from './lib/theme';
import Layout from './components/Layout';
import Login from './pages/Login';
import Dashboard from './pages/Dashboard';
import Accounts from './pages/Accounts';
import ApiKeys from './pages/ApiKeys';
import Emit from './pages/Emit';
import Query from './pages/Query';
import Health from './pages/Health';
import Logs from './pages/Logs';
import Docs from './pages/Docs';
import Playground from './pages/Playground';

applyTheme();

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  return hasKey() ? <>{children}</> : <Navigate to="/login" replace />;
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route element={<ProtectedRoute><Layout /></ProtectedRoute>}>
          <Route path="/" element={<Dashboard />} />
          <Route path="/accounts" element={<Accounts />} />
          <Route path="/keys" element={<ApiKeys />} />
          <Route path="/emit" element={<Emit />} />
          <Route path="/query" element={<Query />} />
          <Route path="/health" element={<Health />} />
          <Route path="/logs" element={<Logs />} />
          <Route path="/docs" element={<Docs />} />
          <Route path="/playground" element={<Playground />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
