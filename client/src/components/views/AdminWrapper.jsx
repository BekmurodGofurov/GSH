import React, { useState, useEffect } from 'react';
import { Loader2 } from 'lucide-react';
import { AdminLoginView } from './AdminLoginView';
import { AdminDashboardView } from './AdminDashboardView';
import { api } from '../../services/api';

export function AdminWrapper({ onExitAdmin }) {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const checkAuth = async () => {
      try {
        const res = await api.verifyAdmin();
        if (res.data?.status === 'authenticated') {
          setIsAuthenticated(true);
        } else {
          setIsAuthenticated(false);
        }
      } catch (e) {
        setIsAuthenticated(false);
      } finally {
        setIsLoading(false);
      }
    };
    checkAuth();
  }, []);

  const handleLogout = async () => {
    await api.adminLogout();
    setIsAuthenticated(false);
  };

  if (isLoading) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[60vh] gap-3 text-slate-400 font-mono text-sm">
        <Loader2 className="w-8 h-8 animate-spin text-cyan-500" />
        <span>Verifying administrative session...</span>
      </div>
    );
  }

  if (isAuthenticated) {
    return (
      <AdminDashboardView
        onLogout={handleLogout}
        onExitAdmin={onExitAdmin}
      />
    );
  }

  return (
    <AdminLoginView
      onLoginSuccess={() => setIsAuthenticated(true)}
      onExitAdmin={onExitAdmin}
    />
  );
}

