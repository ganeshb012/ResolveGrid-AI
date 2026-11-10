import React, { useState, useEffect } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { wsClient } from '../api/ws';
import {
  Shield,
  UserCheck,
  HardHat,
  Cpu,
  Globe,
  Radio,
  LogOut,
  ChevronDown,
  Layers,
  User as UserIcon,
  X,
} from 'lucide-react';
import { Language } from '../i18n/translations';

export const Navbar: React.FC = () => {
  const { user, language, setLanguage, t, logout } = useAuth();
  const location = useLocation();
  const [wsOnline, setWsOnline] = useState<boolean>(true);
  const [profileDropdown, setProfileDropdown] = useState<boolean>(false);
  const [showProfileModal, setShowProfileModal] = useState<boolean>(false);

  useEffect(() => {
    const unsubConnect = wsClient.on('_connected', () => setWsOnline(true));
    const unsubDisconnect = wsClient.on('_disconnected', () => setWsOnline(false));
    return () => {
      unsubConnect();
      unsubDisconnect();
    };
  }, []);

  const allNavLinks = [
    {
      to: '/admin/ai-activity',
      label: t.aiActivityCenter,
      icon: Cpu,
      active: location.pathname.startsWith('/admin/ai-activity'),
      badge: '5 Agents',
      roles: ['ADMIN'],
    },
  ];

  const effectiveRole = user?.role || 'GUEST';
  const navLinks = allNavLinks.filter((item) => item.roles.includes(effectiveRole));
  const isAuthPage = location.pathname === '/login' || location.pathname === '/register';

  return (
    <header className="bg-slate-900 border-b border-slate-800 sticky top-0 z-50 shadow-md w-full">
      <div className="w-full px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">
          {/* Brand Logo */}
          <div className="flex items-center gap-3">
            <Link to="/" className="flex items-center gap-2 group">
              <div className="w-10 h-10 rounded-lg bg-gradient-to-tr from-blue-600 to-indigo-500 flex items-center justify-center shadow-lg shadow-blue-500/20 group-hover:scale-105 transition-transform">
                <Layers className="w-6 h-6 text-white" />
              </div>
              <div>
                <span className="text-xl font-bold bg-gradient-to-r from-blue-400 via-indigo-300 to-teal-300 bg-clip-text text-transparent">
                  ResolveGrid<span className="text-blue-500 text-xs font-mono ml-1 px-1.5 py-0.5 rounded bg-blue-950 border border-blue-800">AI</span>
                </span>
                <p className="text-[10px] text-slate-400 font-mono tracking-wider">
                  PUNE MUNICIPAL SMART CITY
                </p>
              </div>
            </Link>
          </div>

          {/* Navigation Links (Filtered by Role) */}
          <nav className="hidden md:flex items-center space-x-1">
            {navLinks.map((item) => {
              const Icon = item.icon;
              return (
                <Link
                  key={item.to}
                  to={item.to}
                  className={`flex items-center gap-2 px-3.5 py-2 rounded-lg text-sm font-medium transition-all ${
                    item.active
                      ? 'bg-blue-600/20 text-blue-400 border border-blue-500/30 shadow-sm'
                      : 'text-slate-300 hover:text-white hover:bg-slate-800/60'
                  }`}
                >
                  <Icon className={`w-4 h-4 ${item.active ? 'text-blue-400' : 'text-slate-400'}`} />
                  <span>{item.label}</span>
                  {item.badge && (
                    <span className="ml-1 text-[10px] font-semibold px-1.5 py-0.2 rounded-full bg-indigo-500/20 text-indigo-300 border border-indigo-500/30 animate-pulse">
                      {item.badge}
                    </span>
                  )}
                </Link>
              );
            })}
          </nav>

          {/* Right Controls: Role Switcher, Language, Live Status */}
          <div className="flex items-center gap-3">
            {/* Live WebSocket Indicator (Hidden on Login/Register) */}
            {!isAuthPage && (
              <div
                className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-slate-800/80 border border-slate-700/60 text-xs text-slate-300"
                title={wsOnline ? 'Real-time WebSocket Live' : 'Reconnecting WebSocket'}
              >
                <Radio
                  className={`w-3.5 h-3.5 ${
                    wsOnline ? 'text-emerald-400 animate-pulse' : 'text-amber-400'
                  }`}
                />
                <span className="hidden sm:inline font-mono text-[11px]">
                  {wsOnline ? 'LIVE' : 'SYNCING'}
                </span>
              </div>
            )}

            {/* Language Selector (Hidden on Login/Register) */}
            {!isAuthPage && (
              <div className="relative flex items-center bg-slate-800/80 rounded-lg p-0.5 border border-slate-700/60 text-xs">
                <Globe className="w-3.5 h-3.5 ml-2 text-slate-400" />
                {(['en', 'mr', 'hi'] as Language[]).map((lng) => (
                  <button
                    key={lng}
                    onClick={() => setLanguage(lng)}
                    className={`px-2 py-1 rounded text-xs font-medium transition-colors ${
                      language === lng
                        ? 'bg-blue-600 text-white font-bold'
                        : 'text-slate-300 hover:text-white'
                    }`}
                  >
                    {lng === 'en' ? 'EN' : lng === 'mr' ? 'मराठी' : 'हिन्दी'}
                  </button>
                ))}
              </div>
            )}

            {/* User Profile & Authentication Dropdown */}
            {user ? (
              <div className="relative">
                <button
                  onClick={() => setProfileDropdown(!profileDropdown)}
                  className="flex items-center gap-2 px-2.5 py-1.5 bg-slate-800 hover:bg-slate-750 border border-slate-700 rounded-xl text-xs font-medium text-slate-200 transition-colors shadow-sm"
                  aria-label="User profile menu"
                >
                  <div className="w-6 h-6 rounded-lg bg-gradient-to-tr from-blue-600 to-indigo-600 flex items-center justify-center text-white font-bold text-xs shadow">
                    {user.full_name ? user.full_name[0].toUpperCase() : user.role[0]}
                  </div>
                  <div className="hidden sm:flex flex-col text-left">
                    <span className="font-semibold text-slate-200 text-xs leading-none line-clamp-1 max-w-[120px]">
                      {user.full_name || user.email}
                    </span>
                    <span className="text-[10px] text-slate-400 font-mono mt-0.5">
                      {user.role}
                    </span>
                  </div>
                  <ChevronDown className="w-3.5 h-3.5 text-slate-400" />
                </button>

                {profileDropdown && (
                  <div
                    className="absolute right-0 mt-2 w-56 bg-slate-800 border border-slate-700 rounded-2xl shadow-2xl py-2 z-50 text-xs divide-y divide-slate-700/60 backdrop-blur-md"
                    onMouseLeave={() => setProfileDropdown(false)}
                  >
                    {/* User Profile Summary */}
                    <div className="px-3.5 py-2 space-y-0.5">
                      <p className="font-bold text-white text-xs truncate">
                        {user.full_name}
                      </p>
                      <p className="text-[11px] text-slate-400 font-mono truncate">
                        {user.email}
                      </p>
                      <div className="pt-1">
                        <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-blue-950 border border-blue-800 text-blue-300 font-semibold">
                          Role: {user.role}
                        </span>
                      </div>
                    </div>

                    {/* Menu Actions: My Profile & Logout */}
                    <div className="py-1">
                      <button
                        onClick={() => {
                          setShowProfileModal(true);
                          setProfileDropdown(false);
                        }}
                        className="w-full text-left px-3.5 py-2 text-slate-200 hover:bg-slate-700/60 flex items-center gap-2.5 transition-colors font-medium"
                      >
                        <UserIcon className="w-3.5 h-3.5 text-blue-400" />
                        <span>My Profile</span>
                      </button>
                    </div>

                    <div className="pt-1">
                      <button
                        onClick={() => {
                          setProfileDropdown(false);
                          logout();
                        }}
                        className="w-full text-left px-3.5 py-2 text-rose-400 hover:bg-rose-500/10 flex items-center gap-2.5 transition-colors font-semibold"
                      >
                        <LogOut className="w-3.5 h-3.5 text-rose-400" />
                        <span>{t.logout || 'Logout'}</span>
                      </button>
                    </div>
                  </div>
                )}
              </div>
            ) : location.pathname === '/login' || location.pathname === '/register' ? null : (
              <Link
                to="/login"
                className="flex items-center gap-1.5 px-3 py-1.5 bg-blue-600 hover:bg-blue-500 text-white rounded-xl text-xs font-semibold shadow-md shadow-blue-600/20 transition-all"
              >
                <UserCheck className="w-3.5 h-3.5" />
                <span>Sign In</span>
              </Link>
            )}
          </div>
        </div>
      </div>

      {/* My Profile Modal */}
      {showProfileModal && user && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-sm">
          <div className="bg-slate-900 border border-slate-700 rounded-2xl max-w-md w-full p-6 shadow-2xl relative space-y-5">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <div className="flex items-center gap-2.5">
                <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-blue-600 to-indigo-600 flex items-center justify-center text-white font-bold text-base shadow">
                  {user.full_name ? user.full_name[0].toUpperCase() : user.role[0]}
                </div>
                <div>
                  <h3 className="font-bold text-base text-white">My Profile</h3>
                  <p className="text-xs text-slate-400">ResolveGrid AI User Account</p>
                </div>
              </div>
              <button
                onClick={() => setShowProfileModal(false)}
                className="p-1 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition-colors"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="space-y-3 text-xs">
              <div className="p-3 bg-slate-950/70 rounded-xl border border-slate-800 space-y-1">
                <span className="text-[10px] text-slate-500 uppercase font-semibold">Full Name</span>
                <p className="font-medium text-slate-100 text-sm">{user.full_name || 'N/A'}</p>
              </div>

              <div className="p-3 bg-slate-950/70 rounded-xl border border-slate-800 space-y-1">
                <span className="text-[10px] text-slate-500 uppercase font-semibold">Email Address</span>
                <p className="font-mono text-slate-200">{user.email}</p>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div className="p-3 bg-slate-950/70 rounded-xl border border-slate-800 space-y-1">
                  <span className="text-[10px] text-slate-500 uppercase font-semibold">System Role</span>
                  <p className="font-bold text-blue-400 font-mono">{user.role}</p>
                </div>

                <div className="p-3 bg-slate-950/70 rounded-xl border border-slate-800 space-y-1">
                  <span className="text-[10px] text-slate-500 uppercase font-semibold">Language</span>
                  <p className="font-medium text-slate-200 uppercase">{user.preferred_language || 'EN'}</p>
                </div>
              </div>

              <div className="p-3 bg-slate-950/70 rounded-xl border border-slate-800 space-y-1">
                <span className="text-[10px] text-slate-500 uppercase font-semibold">User Identifier</span>
                <p className="font-mono text-[10px] text-slate-400 truncate">{user.id}</p>
              </div>
            </div>

            <div className="pt-2 flex items-center justify-end gap-2">
              <button
                onClick={() => setShowProfileModal(false)}
                className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-200 rounded-xl text-xs font-semibold transition-colors"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </header>
  );
};

export default Navbar;
