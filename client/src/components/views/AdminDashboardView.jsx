import React, { useState, useEffect } from 'react';
import { api } from '../../services/api';

export function AdminDashboardView() {
  const [servers, setServers] = useState([]);
  const [formData, setFormData] = useState({ server_id: '', server_name: '', region: 'EU-East' });
  const [error, setError] = useState(null);

  const fetchServers = async () => {
    const res = await api.getServers(true);
    if (res.data) setServers(res.data);
  };

  useEffect(() => {
    fetchServers();
  }, []);

  const handleAdd = async (e) => {
    e.preventDefault();
    const res = await api.addServer(formData);
    if (res.error) setError(res.error);
    else {
      setFormData({ server_id: '', server_name: '', region: 'EU-East' });
      fetchServers();
    }
  };

  const handleUpdate = async (serverId) => {
    const newName = prompt("New server name:");
    const newRegion = prompt("New region:");
    if (!newName || !newRegion) return;
    const res = await api.updateServer(serverId, { server_id: serverId, server_name: newName, region: newRegion });
    if (res.error) alert(res.error);
    else fetchServers();
  };

  const handleDelete = async (serverId) => {
    if (confirm("Are you sure you want to delete " + serverId + "?")) {
      const res = await api.deleteServer(serverId);
      if (res.error) alert(res.error);
      else fetchServers();
    }
  };

  return (
    <div className="space-y-6">
      <h2 className="text-2xl font-bold">Admin Dashboard</h2>
      {error && <p className="text-red-500">{error}</p>}
      
      <div className="bg-slate-800 p-4 rounded-lg">
        <h3 className="font-bold mb-2">Add New Server</h3>
        <form className="flex space-x-2" onSubmit={handleAdd}>
          <input className="px-2 py-1 rounded text-black" placeholder="IP:Port" value={formData.server_id} onChange={e => setFormData({...formData, server_id: e.target.value})} />
          <input className="px-2 py-1 rounded text-black" placeholder="Name" value={formData.server_name} onChange={e => setFormData({...formData, server_name: e.target.value})} />
          <input className="px-2 py-1 rounded text-black" placeholder="Region" value={formData.region} onChange={e => setFormData({...formData, region: e.target.value})} />
          <button type="submit" className="bg-green-600 px-3 py-1 rounded text-white">Add</button>
        </form>
      </div>

      <div className="bg-slate-800 p-4 rounded-lg">
        <h3 className="font-bold mb-2">Manage Servers</h3>
        <ul className="space-y-2">
          {servers.map(s => (
            <li key={s.server_id} className="flex justify-between border-b border-slate-700 pb-2">
              <span>{s.server_name} ({s.server_id}) - {s.region}</span>
              <div className="space-x-2">
                <button onClick={() => handleUpdate(s.server_id)} className="bg-blue-600 px-2 py-1 text-xs rounded text-white">Edit</button>
                <button onClick={() => handleDelete(s.server_id)} className="bg-red-600 px-2 py-1 text-xs rounded text-white">Delete</button>
              </div>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
