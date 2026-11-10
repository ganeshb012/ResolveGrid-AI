import React from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { UserRole } from '../types';

interface ProtectedRouteProps {
  children: React.ReactElement;
  allowedRoles: UserRole[];
}

export const ProtectedRoute: React.FC<ProtectedRouteProps> = ({ children, allowedRoles }) => {
  const { user, isLoading } = useAuth();
  const location = useLocation();

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <div className="flex flex-col items-center gap-3">
          <div className="w-8 h-8 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
          <span className="text-xs text-slate-400 font-mono">Restoring authenticated session...</span>
        </div>
      </div>
    );
  }

  // Unauthenticated users visiting protected routes must be redirected to /login
  if (!user) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  // Check if current user's role is permitted
  if (!allowedRoles.includes(user.role)) {
    // Role-specific redirect rules:
    // - CITIZEN users visiting /worker must be redirected to /citizen
    // - CITIZEN and WORKER users visiting /admin must be redirected to their appropriate portal
    if (user.role === 'WORKER') {
      return <Navigate to="/worker" replace />;
    }
    return <Navigate to="/citizen" replace />;
  }

  return children;
};

export default ProtectedRoute;

