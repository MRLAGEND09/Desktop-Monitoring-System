import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import { Suspense, lazy } from 'react';
import { useAuthStore } from './store/auth';
import Layout from './components/Layout';

// Eagerly load Login (tiny, always needed first)
import LoginPage from './pages/LoginPage';

// Lazy-load all main pages — each becomes its own JS chunk
const DashboardPage = lazy(() => import('./pages/DashboardPage'));
const DevicePage    = lazy(() => import('./pages/DevicePage'));
const AlertsPage    = lazy(() => import('./pages/AlertsPage'));
const LogsPage      = lazy(() => import('./pages/LogsPage'));
const UsersPage     = lazy(() => import('./pages/UsersPage'));
const WebhooksPage  = lazy(() => import('./pages/WebhooksPage'));

function PageLoader() {
  return (
    <div className="flex items-center justify-center h-full text-gray-400">
      Loading…
    </div>
  );
}

function PrivateRoute({ children }) {
  const token = useAuthStore((s) => s.token);
  return token ? children : <Navigate to="/login" replace />;
}

function AdminRoute({ children }) {
  const user = useAuthStore((s) => s.user);
  return user?.role === 'admin' ? children : <Navigate to="/" replace />;
}

export default function App() {
  return (
    <BrowserRouter>
      <Suspense fallback={<PageLoader />}>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/" element={<PrivateRoute><Layout /></PrivateRoute>}>
            <Route index              element={<DashboardPage />} />
            <Route path="device/:deviceId" element={<DevicePage />} />
            <Route path="alerts"      element={<AlertsPage />} />
            <Route path="logs"        element={<LogsPage />} />
            <Route path="users"       element={<AdminRoute><UsersPage /></AdminRoute>} />
            <Route path="webhooks"    element={<AdminRoute><WebhooksPage /></AdminRoute>} />
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </Suspense>
    </BrowserRouter>
  );
}
