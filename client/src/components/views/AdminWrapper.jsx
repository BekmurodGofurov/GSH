import React, { useState, useEffect } from 'react';
import { AdminLoginView } from './AdminLoginView';
import { AdminDashboardView } from './AdminDashboardView';
import { api } from '../../services/api';

export function AdminWrapper() {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const checkAuth = async () => {
      const res = await api.verifyAdmin();
      if (res.data?.status === 'authenticated') {
        setIsAuthenticated(true);
      } else {
        setIsAuthenticated(false);
      }
      setIsLoading(false);
    };
    checkAuth();
  }, []);

  const handleLogout = async () => {
    await api.adminLogout();
    setIsAuthenticated(false);
  };

  if (isLoading) {
    return <div className="p-8 text-center">Checking authentication...</div>;
  }

  if (isAuthenticated) {
    return (
      <div>
        <div className="flex justify-end mb-4">
          <button onClick={handleLogout} className="bg-slate-700 hover:bg-slate-600 px-4 py-2 rounded text-white text-sm">
            Logout
          </button>
        </div>
        <AdminDashboardView />
      </div>
    );
  }

  return <AdminLoginView onLoginSuccess={() => setIsAuthenticated(true)} />;
}
