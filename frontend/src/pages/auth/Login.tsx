import React, { useState } from 'react';
import { useNavigate, useLocation, useSearchParams, Link } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import { api } from '../../api/client';
import { UserRole } from '../../types';
import {
  Lock,
  Mail,
  ArrowRight,
  Layers,
  Eye,
  EyeOff,
  User,
  HardHat,
  Shield,
  CheckCircle2,
} from 'lucide-react';

export const Login: React.FC = () => {
  const { login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [searchParams] = useSearchParams();

  // Detect active portal based on URL query param or redirection origin
  const initialPortal = (searchParams.get('portal') as 'citizen' | 'worker' | 'admin') ||
    (location.state?.from?.pathname?.startsWith('/worker')
      ? 'worker'
      : location.state?.from?.pathname?.startsWith('/admin')
      ? 'admin'
      : 'citizen');

  const [activePortal, setActivePortal] = useState<'citizen' | 'worker' | 'admin'>(initialPortal);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handlePortalSwitch = (portal: 'citizen' | 'worker' | 'admin') => {
    setActivePortal(portal);
    setError(null);
  };

  const handleAutofill = (role: 'citizen' | 'worker' | 'admin') => {
    setActivePortal(role);
    if (role === 'citizen') {
      setEmail('citizen@resolvegrid.gov.in');
      setPassword('Citizen@12345');
    } else if (role === 'worker') {
      setEmail('worker@resolvegrid.gov.in');
      setPassword('Worker@12345');
    } else {
      setEmail('admin@resolvegrid.gov.in');
      setPassword('Admin@12345');
    }
    setError(null);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    setError(null);

    try {
      const res = await api.auth.login({ email, password });
      login(res.access_token, {
        id: res.user_id,
        email: res.email,
        full_name: res.full_name,
        role: res.role as UserRole,
        preferred_language: res.preferred_language || 'en',
        is_active: true,
        created_at: new Date().toISOString(),
      });

      if (res.role === 'ADMIN') navigate('/admin');
      else if (res.role === 'WORKER') navigate('/worker');
      else navigate('/citizen');
    } catch (err: any) {
      console.error('Login error:', err);
      setError(err.response?.data?.detail || 'Invalid email or password.');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-[85vh] flex items-center justify-center px-4 py-12 relative">
      {/* Soft Ambient Municipal Lighting */}
      <div className="absolute top-1/4 left-1/3 w-80 h-80 bg-blue-600/10 rounded-full blur-3xl pointer-events-none" />
      <div className="absolute bottom-1/4 right-1/3 w-80 h-80 bg-indigo-600/10 rounded-full blur-3xl pointer-events-none" />

      <div className="max-w-md w-full relative z-10">
        <div className="bg-slate-900/80 border border-slate-700/80 rounded-3xl p-8 sm:p-9 shadow-2xl backdrop-blur-xl space-y-6">
          
          {/* Brand Header */}
          <div className="text-center space-y-2">
            <div className="inline-flex p-3 rounded-2xl bg-gradient-to-tr from-blue-600 to-indigo-600 shadow-xl shadow-blue-500/25 text-white mb-1 ring-4 ring-blue-500/10">
              <Layers className="w-7 h-7" />
            </div>
            <h1 className="text-2xl font-extrabold text-white tracking-tight">
              {activePortal === 'citizen'
                ? 'Sign In to Citizen Portal'
                : activePortal === 'worker'
                ? 'Field Crew Terminal Sign In'
                : 'PMC Operations Command Sign In'}
            </h1>
            <p className="text-xs text-slate-400 max-w-xs mx-auto">
              {activePortal === 'citizen'
                ? 'Pune Municipal Corporation Infrastructure & Public Grievance Portal'
                : activePortal === 'worker'
                ? 'PMC Rapid Response Field Unit & Maintenance Dispatch Access'
                : 'Municipal Multi-Agent Supervisory Control & Analytics Center'}
            </p>
          </div>

          {/* Portal Switcher Tabs */}
          <div className="grid grid-cols-3 gap-1.5 p-1 bg-slate-950/80 rounded-2xl border border-slate-800">
            <button
              type="button"
              onClick={() => handlePortalSwitch('citizen')}
              className={`py-2 px-2 rounded-xl text-xs font-bold transition-all flex items-center justify-center gap-1.5 ${
                activePortal === 'citizen'
                  ? 'bg-blue-600 text-white shadow-md shadow-blue-600/30'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              <User className="w-3.5 h-3.5" />
              <span>Citizen</span>
            </button>
            <button
              type="button"
              onClick={() => handlePortalSwitch('worker')}
              className={`py-2 px-2 rounded-xl text-xs font-bold transition-all flex items-center justify-center gap-1.5 ${
                activePortal === 'worker'
                  ? 'bg-amber-500 text-slate-950 font-extrabold shadow-md shadow-amber-500/20'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              <HardHat className="w-3.5 h-3.5" />
              <span>Field Crew</span>
            </button>
            <button
              type="button"
              onClick={() => handlePortalSwitch('admin')}
              className={`py-2 px-2 rounded-xl text-xs font-bold transition-all flex items-center justify-center gap-1.5 ${
                activePortal === 'admin'
                  ? 'bg-indigo-600 text-white shadow-md shadow-indigo-600/30'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              <Shield className="w-3.5 h-3.5" />
              <span>Admin Ops</span>
            </button>
          </div>

          {/* Quick Demo Credentials Autofill Helper */}
          <div className="bg-slate-950/60 border border-slate-800/80 rounded-xl px-3 py-2 flex items-center justify-between text-[11px] text-slate-400">
            <span>Demo credentials:</span>
            <button
              type="button"
              onClick={() => handleAutofill(activePortal)}
              className="font-mono text-blue-400 hover:text-blue-300 font-semibold underline"
            >
              Fill {activePortal.toUpperCase()} Demo
            </button>
          </div>

          {error && (
            <div className="p-3 bg-rose-950/50 border border-rose-500/40 rounded-xl text-xs text-rose-300">
              {error}
            </div>
          )}

          {/* Login Form */}
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1.5">
                Email Address
              </label>
              <div className="relative">
                <Mail className="w-4 h-4 absolute left-3.5 top-3.5 text-slate-400 pointer-events-none" />
                <input
                  type="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="name@example.com"
                  className="w-full pl-10 pr-4 py-2.5 bg-slate-950/90 border border-slate-700/80 rounded-xl text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 transition-all"
                />
              </div>
            </div>

            <div>
              <div className="flex items-center justify-between mb-1.5">
                <label className="block text-xs font-semibold text-slate-300">
                  Password
                </label>
                <span className="text-[11px] text-slate-500 font-mono">PMC Auth</span>
              </div>
              
              <div className="relative">
                <Lock className="w-4 h-4 absolute left-3.5 top-3.5 text-slate-400 pointer-events-none" />
                <input
                  type={showPassword ? 'text' : 'password'}
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••"
                  className="w-full pl-10 pr-11 py-2.5 bg-slate-950/90 border border-slate-700/80 rounded-xl text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 transition-all font-mono"
                />
                
                {/* SHOW / HIDE PASSWORD TOGGLE BUTTON */}
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  title={showPassword ? 'Hide password' : 'Show password'}
                  className="absolute right-3 top-2.5 p-1 text-slate-400 hover:text-white rounded-lg hover:bg-slate-800 transition-colors focus:outline-none"
                  aria-label="Toggle password visibility"
                >
                  {showPassword ? (
                    <EyeOff className="w-4 h-4 text-amber-400" />
                  ) : (
                    <Eye className="w-4 h-4" />
                  )}
                </button>
              </div>
            </div>

            <button
              type="submit"
              disabled={isLoading}
              className="w-full py-3.5 rounded-xl bg-gradient-to-r from-blue-600 via-indigo-600 to-blue-500 hover:from-blue-500 hover:to-indigo-500 active:scale-[0.99] text-white font-bold text-sm shadow-xl shadow-blue-600/30 transition-all flex items-center justify-center gap-2 disabled:opacity-50"
            >
              <span>{isLoading ? 'Authenticating...' : 'Sign In'}</span>
              <ArrowRight className="w-4 h-4" />
            </button>
          </form>

          {/* Citizen Registration Link ONLY shown on Citizen Login Page */}
          {activePortal === 'citizen' ? (
            <div className="pt-2 text-center border-t border-slate-800/80">
              <p className="text-xs text-slate-400">
                New citizen?{' '}
                <Link
                  to="/register"
                  className="text-blue-400 hover:text-blue-300 font-bold hover:underline transition-colors"
                >
                  Register here
                </Link>
              </p>
            </div>
          ) : (
            <div className="pt-2 text-center border-t border-slate-800/80">
              <p className="text-[11px] text-slate-500 font-mono flex items-center justify-center gap-1.5">
                <Shield className="w-3.5 h-3.5 text-slate-400" />
                <span>
                  {activePortal === 'worker'
                    ? 'Field Crew accounts are provisioned by PMC Ward Officers.'
                    : 'Restricted to authorized Pune Municipal Administrators.'}
                </span>
              </p>
            </div>
          )}

        </div>

        {/* Security Badge */}
        <div className="mt-4 flex items-center justify-center gap-3 text-[11px] text-slate-500">
          <span className="flex items-center gap-1">
            <CheckCircle2 className="w-3 h-3 text-emerald-400" />
            256-bit Municipal SSL
          </span>
          <span>•</span>
          <span className="font-mono">JWT Role Enforced</span>
        </div>
      </div>
    </div>
  );
};
