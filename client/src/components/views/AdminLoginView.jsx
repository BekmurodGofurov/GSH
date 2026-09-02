import React, { useState } from 'react';
import { api } from '../../services/api';

export function AdminLoginView({ onLoginSuccess }) {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState(null);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(null);
    const res = await api.adminLogin(username, password);
    if (res.error) {
      setError(res.error);
    } else {
      onLoginSuccess();
    }
  };

  return (
    <div className="flex flex-col items-center justify-center min-h-[50vh]">
      <h2 className="text-2xl font-bold mb-4">Admin Login</h2>
      <form className="flex flex-col space-y-4 w-64" onSubmit={handleSubmit}>
        <input 
          type="text" 
          placeholder="Username" 
          value={username} 
          onChange={(e) => setUsername(e.target.value)}
          className="px-3 py-2 border rounded bg-slate-800 text-white"
        />
        <input 
          type="password" 
          placeholder="Password" 
          value={password} 
          onChange={(e) => setPassword(e.target.value)}
          className="px-3 py-2 border rounded bg-slate-800 text-white"
        />
        <button type="submit" className="bg-cyan-600 px-4 py-2 rounded text-white font-bold">
          Login
        </button>
      </form>
      {error && <p className="text-red-500 mt-4">{error}</p>}
    </div>
  );
}
