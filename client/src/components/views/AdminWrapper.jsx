import React, { useState, useEffect } from 'react';
import { AdminLoginView } from './AdminLoginView';
import { AdminDashboardView } from './AdminDashboardView';

export function AdminWrapper() {
  const [isAuthenticated, setIsAuthenticated] = useState(false);

  useEffect(() => {
    const token = localStorage.getItem('admin_token');
    if (token) {
      setIsAuthenticated(true);
    }
  }, []);

  if (isAuthenticated) {
    return <AdminDashboardView />;
  }

  return <AdminLoginView onLoginSuccess={() => setIsAuthenticated(true)} />;
}
