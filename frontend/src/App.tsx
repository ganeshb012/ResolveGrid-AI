import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider } from './context/AuthContext';
import { Navbar } from './components/Navbar';
import { ProtectedRoute } from './components/ProtectedRoute';
import { CitizenPortal } from './pages/citizen/CitizenPortal';
import { AdminDashboard } from './pages/admin/AdminDashboard';
import { AIActivityCenter } from './pages/ai-activity/AIActivityCenter';
import { WorkerPortal } from './pages/worker/WorkerPortal';
import { Login } from './pages/auth/Login';
import { Register } from './pages/auth/Register';

export const AppContent: React.FC = () => {
  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col font-sans selection:bg-blue-600 selection:text-white">
      <Navbar />
      <main className="flex-1">
        <Routes>
          <Route path="/" element={<CitizenPortal />} />
          <Route path="/citizen" element={<CitizenPortal />} />
          <Route
            path="/worker"
            element={
              <ProtectedRoute allowedRoles={['WORKER', 'ADMIN']}>
                <WorkerPortal />
              </ProtectedRoute>
            }
          />
          <Route
            path="/admin"
            element={
              <ProtectedRoute allowedRoles={['ADMIN']}>
                <AdminDashboard />
              </ProtectedRoute>
            }
          />
          <Route
            path="/admin/ai-activity"
            element={
              <ProtectedRoute allowedRoles={['ADMIN']}>
                <AIActivityCenter />
              </ProtectedRoute>
            }
          />
          <Route path="/login" element={<Login />} />
          <Route path="/register" element={<Register />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </main>

      {/* Footer */}
      <footer className="border-t border-slate-900 bg-slate-950/80 py-6 text-center text-xs text-slate-500">
        <div className="w-full px-4 sm:px-6 lg:px-8 flex flex-col sm:flex-row items-center justify-between gap-2">
          <p>© 2026 ResolveGrid AI — Pune Municipal Corporation Infrastructure Incident System</p>
          <div className="flex items-center gap-4 text-slate-400">
            <span>Prisma STT</span>
            <span>•</span>
            <span>Evon Reasoning</span>
            <span>•</span>
            <span>Timbre TTS</span>
            <span>•</span>
            <span>Warp S2S</span>
          </div>
        </div>
      </footer>
    </div>
  );
};

export const App: React.FC = () => {
  return (
    <BrowserRouter>
      <AuthProvider>
        <AppContent />
      </AuthProvider>
    </BrowserRouter>
  );
};

export default App;
