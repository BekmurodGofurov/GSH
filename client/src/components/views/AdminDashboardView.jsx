import React, { useState, useEffect, useMemo } from 'react';
import {
  Server,
  Plus,
  Pencil,
  Trash2,
  Copy,
  Check,
  Search,
  Globe,
  RefreshCw,
  ShieldCheck,
  ArrowLeft,
  LogOut,
  AlertCircle,
  CheckCircle2,
  Activity,
  MapPin,
  SlidersHorizontal,
  X,
  Loader2,
} from 'lucide-react';
import { api } from '../../services/api';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../common/Card';
import { Button } from '../common/Button';
import { Badge } from '../common/Badge';
import { Modal } from '../common/Modal';
import { Input, Select } from '../common/Input';

const STANDARD_REGIONS = [
  { value: 'Vienna', label: 'Vienna (Central Europe)' },
  { value: 'Warsaw', label: 'Warsaw (Poland)' },
  { value: 'EU-East', label: 'EU-East (Eastern Europe)' },
  { value: 'Frankfurt', label: 'Frankfurt (Germany)' },
  { value: 'London', label: 'London (United Kingdom)' },
  { value: 'Helsinki', label: 'Helsinki (Finland)' },
  { value: 'Stockholm', label: 'Stockholm (Sweden)' },
  { value: 'Paris', label: 'Paris (France)' },
  { value: 'Madrid', label: 'Madrid (Spain)' },
  { value: '__custom__', label: '+ Other / Custom Region...' },
];

export function AdminDashboardView({ onLogout, onExitAdmin }) {
  const [servers, setServers] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [feedback, setFeedback] = useState(null); // { type: 'success'|'error', message: '' }
  const [copiedId, setCopiedId] = useState(null);

  // Search and filter
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedRegionFilter, setSelectedRegionFilter] = useState('ALL');

  // Add Server Modal state
  const [isAddModalOpen, setIsAddModalOpen] = useState(false);
  const [addIp, setAddIp] = useState('');
  const [addPort, setAddPort] = useState('27015');
  const [addName, setAddName] = useState('');
  const [addRegion, setAddRegion] = useState('Vienna');
  const [addCustomRegion, setAddCustomRegion] = useState('');
  const [isSubmittingAdd, setIsSubmittingAdd] = useState(false);

  // Edit Server Modal state
  const [editingServer, setEditingServer] = useState(null);
  const [editName, setEditName] = useState('');
  const [editRegion, setEditRegion] = useState('Vienna');
  const [editCustomRegion, setEditCustomRegion] = useState('');
  const [isSubmittingEdit, setIsSubmittingEdit] = useState(false);

  // Delete Server Modal state
  const [deletingServer, setDeletingServer] = useState(null);
  const [isSubmittingDelete, setIsSubmittingDelete] = useState(false);

  // Fetch servers from gateway
  const fetchServers = async (showLoading = false) => {
    if (showLoading) setIsLoading(true);
    setIsRefreshing(true);
    try {
      const res = await api.getServers(true);
      if (res.data) {
        setServers(res.data);
      } else if (res.error) {
        showFeedback('error', res.error);
      }
    } catch (err) {
      showFeedback('error', 'Failed to retrieve server fleet data.');
    } finally {
      setIsLoading(false);
      setIsRefreshing(false);
    }
  };

  useEffect(() => {
    fetchServers(true);
  }, []);

  const showFeedback = (type, message) => {
    setFeedback({ type, message });
    setTimeout(() => {
      setFeedback((prev) => (prev?.message === message ? null : prev));
    }, 4500);
  };

  const handleCopyIp = (ipPort) => {
    navigator.clipboard.writeText(ipPort);
    setCopiedId(ipPort);
    setTimeout(() => setCopiedId(null), 2000);
  };

  // Compile full region options combining predefined list and existing DB regions
  const availableRegions = useMemo(() => {
    const existing = new Set(servers.map((s) => s.region).filter(Boolean));
    const list = [...STANDARD_REGIONS];
    existing.forEach((r) => {
      if (!list.some((item) => item.value === r)) {
        list.splice(list.length - 1, 0, { value: r, label: `${r} (Existing)` });
      }
    });
    return list;
  }, [servers]);

  // Handle Add form IP auto-split if user pastes "IP:PORT"
  const handleAddIpChange = (val) => {
    if (val.includes(':')) {
      const [pIp, pPort] = val.split(':');
      setAddIp(pIp.trim());
      if (pPort) setAddPort(pPort.trim());
    } else {
      setAddIp(val);
    }
  };

  // Submit Add Server
  const handleAddSubmit = async (e) => {
    e.preventDefault();
    const cleanIp = addIp.trim();
    const cleanPort = addPort.trim() || '27015';
    const serverId = `${cleanIp}:${cleanPort}`;
    const finalRegion = addRegion === '__custom__' ? addCustomRegion.trim() : addRegion;

    if (!cleanIp || !addName.trim() || !finalRegion) {
      showFeedback('error', 'Please fill in IP address, Server Name, and Region.');
      return;
    }

    setIsSubmittingAdd(true);
    try {
      const res = await api.addServer({
        server_id: serverId,
        server_name: addName.trim(),
        region: finalRegion,
      });

      if (res.error) {
        showFeedback('error', res.error);
      } else {
        showFeedback('success', `Server ${serverId} added successfully.`);
        setIsAddModalOpen(false);
        setAddIp('');
        setAddPort('27015');
        setAddName('');
        setAddRegion('Vienna');
        setAddCustomRegion('');
        await fetchServers();
      }
    } catch (err) {
      showFeedback('error', 'Failed to add new monitored server.');
    } finally {
      setIsSubmittingAdd(false);
    }
  };

  // Open Edit Modal
  const handleOpenEdit = (server) => {
    setEditingServer(server);
    setEditName(server.server_name || '');
    const hasPreset = availableRegions.some((r) => r.value === server.region);
    if (hasPreset) {
      setEditRegion(server.region);
      setEditCustomRegion('');
    } else {
      setEditRegion('__custom__');
      setEditCustomRegion(server.region || '');
    }
  };

  // Submit Edit Server
  const handleEditSubmit = async (e) => {
    e.preventDefault();
    if (!editingServer) return;

    const finalRegion = editRegion === '__custom__' ? editCustomRegion.trim() : editRegion;
    if (!editName.trim() || !finalRegion) {
      showFeedback('error', 'Server Name and Region cannot be empty.');
      return;
    }

    setIsSubmittingEdit(true);
    try {
      const res = await api.updateServer(editingServer.server_id, {
        server_id: editingServer.server_id,
        server_name: editName.trim(),
        region: finalRegion,
      });

      if (res.error) {
        showFeedback('error', res.error);
      } else {
        showFeedback('success', `Server ${editingServer.server_id} updated.`);
        setEditingServer(null);
        await fetchServers();
      }
    } catch (err) {
      showFeedback('error', 'Failed to update server.');
    } finally {
      setIsSubmittingEdit(false);
    }
  };

  // Submit Delete Server
  const handleDeleteSubmit = async () => {
    if (!deletingServer) return;

    setIsSubmittingDelete(true);
    try {
      const res = await api.deleteServer(deletingServer.server_id);
      if (res.error) {
        showFeedback('error', res.error);
      } else {
        showFeedback('success', `Server ${deletingServer.server_id} removed from monitoring.`);
        setDeletingServer(null);
        await fetchServers();
      }
    } catch (err) {
      showFeedback('error', 'Failed to delete server.');
    } finally {
      setIsSubmittingDelete(false);
    }
  };

  // Filtered servers based on search and region
  const filteredServers = useMemo(() => {
    return servers.filter((s) => {
      const matchesSearch =
        !searchQuery ||
        s.server_name?.toLowerCase().includes(searchQuery.toLowerCase()) ||
        s.server_id?.toLowerCase().includes(searchQuery.toLowerCase()) ||
        s.region?.toLowerCase().includes(searchQuery.toLowerCase());

      const matchesRegion =
        selectedRegionFilter === 'ALL' || s.region === selectedRegionFilter;

      return matchesSearch && matchesRegion;
    });
  }, [servers, searchQuery, selectedRegionFilter]);

  const onlineCount = servers.filter((s) => s.status === 'ONLINE').length;
  const offlineCount = servers.filter((s) => s.status === 'OFFLINE').length;

  return (
    <div className="space-y-6 max-w-7xl mx-auto pb-12">
      {/* Top Banner / Navigation & Actions */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-2 border-b border-slate-200 dark:border-slate-800">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-cyan-500/10 border border-cyan-500/30 flex items-center justify-center text-cyan-600 dark:text-cyan-400 shadow-sm">
            <ShieldCheck className="w-5 h-5" />
          </div>
          <div>
            <div className="flex items-center gap-2.5">
              <h1 className="text-xl sm:text-2xl font-bold text-slate-900 dark:text-slate-100 tracking-tight">
                Server Fleet Administration
              </h1>
              <Badge variant="cyan" size="sm" className="hidden sm:inline-flex font-semibold">
                ADMIN CONSOLE
              </Badge>
            </div>
            <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
              Configure monitored Counter-Strike 2 dedicated nodes, ports, and regional targets.
            </p>
          </div>
        </div>

        {/* Global Admin Actions */}
        <div className="flex items-center flex-wrap gap-2.5">
          {onExitAdmin && (
            <Button
              variant="outline"
              size="sm"
              icon={ArrowLeft}
              onClick={onExitAdmin}
              className="text-xs"
            >
              Public Monitor
            </Button>
          )}

          <Button
            variant="outline"
            size="sm"
            icon={RefreshCw}
            loading={isRefreshing}
            onClick={() => fetchServers(false)}
            className="text-xs"
          >
            Refresh
          </Button>

          <Button
            variant="primary"
            size="sm"
            icon={Plus}
            onClick={() => setIsAddModalOpen(true)}
            className="text-xs font-semibold"
          >
            Add New Server
          </Button>

          {onLogout && (
            <Button
              variant="ghost"
              size="sm"
              icon={LogOut}
              onClick={onLogout}
              className="text-xs text-rose-500 hover:text-rose-600 hover:bg-rose-50 dark:hover:bg-rose-500/10"
            >
              Logout
            </Button>
          )}
        </div>
      </div>

      {/* Floating Alert / Toast feedback */}
      {feedback && (
        <div
          className={`p-3.5 rounded-xl border flex items-center justify-between gap-3 text-xs font-medium animate-fade-in shadow-lg ${
            feedback.type === 'success'
              ? 'bg-emerald-50 text-emerald-800 border-emerald-300 dark:bg-emerald-950/80 dark:text-emerald-300 dark:border-emerald-500/40'
              : 'bg-rose-50 text-rose-800 border-rose-300 dark:bg-rose-950/80 dark:text-rose-300 dark:border-rose-500/40'
          }`}
        >
          <div className="flex items-center gap-2">
            {feedback.type === 'success' ? (
              <CheckCircle2 className="w-4 h-4 text-emerald-600 dark:text-emerald-400 flex-shrink-0" />
            ) : (
              <AlertCircle className="w-4 h-4 text-rose-600 dark:text-rose-400 flex-shrink-0" />
            )}
            <span>{feedback.message}</span>
          </div>
          <button
            onClick={() => setFeedback(null)}
            className="text-slate-400 hover:text-slate-600 dark:hover:text-slate-200"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      {/* Metrics / Status Snapshot Cards */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <Card className="bg-slate-50/50 dark:bg-slate-900/40">
          <CardContent className="p-3.5 sm:p-4">
            <span className="text-[11px] font-mono text-slate-500 dark:text-slate-400 uppercase tracking-wider block">
              Total Monitored
            </span>
            <div className="text-xl sm:text-2xl font-bold font-mono text-slate-900 dark:text-slate-100 mt-1">
              {servers.length} <span className="text-xs font-normal text-slate-400">nodes</span>
            </div>
          </CardContent>
        </Card>

        <Card className="bg-slate-50/50 dark:bg-slate-900/40">
          <CardContent className="p-3.5 sm:p-4">
            <span className="text-[11px] font-mono text-emerald-600 dark:text-emerald-400 uppercase tracking-wider block">
              Online Nodes
            </span>
            <div className="text-xl sm:text-2xl font-bold font-mono text-emerald-600 dark:text-emerald-400 mt-1">
              {onlineCount} <span className="text-xs font-normal text-slate-400">active</span>
            </div>
          </CardContent>
        </Card>

        <Card className="bg-slate-50/50 dark:bg-slate-900/40">
          <CardContent className="p-3.5 sm:p-4">
            <span className="text-[11px] font-mono text-rose-600 dark:text-rose-400 uppercase tracking-wider block">
              Offline Nodes
            </span>
            <div className="text-xl sm:text-2xl font-bold font-mono text-rose-600 dark:text-rose-400 mt-1">
              {offlineCount} <span className="text-xs font-normal text-slate-400">down</span>
            </div>
          </CardContent>
        </Card>

        <Card className="bg-slate-50/50 dark:bg-slate-900/40">
          <CardContent className="p-3.5 sm:p-4">
            <span className="text-[11px] font-mono text-cyan-600 dark:text-cyan-400 uppercase tracking-wider block">
              Target Regions
            </span>
            <div className="text-xl sm:text-2xl font-bold font-mono text-cyan-600 dark:text-cyan-400 mt-1">
              {new Set(servers.map((s) => s.region)).size}{' '}
              <span className="text-xs font-normal text-slate-400">zones</span>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Main Server Fleet Table Card */}
      <Card>
        <CardHeader className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-slate-100 dark:border-slate-800">
          <div>
            <CardTitle icon={Server} className="text-base sm:text-lg">
              Registered Game Servers
            </CardTitle>
            <CardDescription>
              Showing {filteredServers.length} of {servers.length} monitored CS2 nodes.
            </CardDescription>
          </div>

          {/* Search & Region Filter Bar */}
          <div className="flex flex-wrap items-center gap-2.5 w-full sm:w-auto">
            <div className="w-full sm:w-60">
              <Input
                icon={Search}
                placeholder="Filter by name, IP, region..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                clearable
                onClear={() => setSearchQuery('')}
                className="py-1.5 text-xs"
              />
            </div>

            <div className="w-full sm:w-44">
              <select
                value={selectedRegionFilter}
                onChange={(e) => setSelectedRegionFilter(e.target.value)}
                className="w-full bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700/80 rounded-lg px-2.5 py-1.5 text-xs text-slate-900 dark:text-slate-200 outline-none focus:border-cyan-500 font-mono cursor-pointer"
              >
                <option value="ALL">All Regions (All)</option>
                {Array.from(new Set(servers.map((s) => s.region).filter(Boolean))).map((r) => (
                  <option key={r} value={r}>
                    {r}
                  </option>
                ))}
              </select>
            </div>
          </div>
        </CardHeader>

        {isLoading ? (
          <div className="p-12 text-center text-slate-400 font-mono text-sm flex flex-col items-center justify-center gap-2">
            <Loader2 className="w-6 h-6 animate-spin text-cyan-500" />
            <span>Loading registered server fleet...</span>
          </div>
        ) : filteredServers.length === 0 ? (
          <div className="p-12 text-center text-slate-400 font-mono text-sm flex flex-col items-center justify-center gap-3">
            <Server className="w-10 h-10 text-slate-500 stroke-1" />
            <p className="text-slate-300 font-semibold">No game servers match your filter.</p>
            {(searchQuery || selectedRegionFilter !== 'ALL') && (
              <Button
                variant="outline"
                size="sm"
                onClick={() => {
                  setSearchQuery('');
                  setSelectedRegionFilter('ALL');
                }}
                className="text-xs"
              >
                Clear Search & Filters
              </Button>
            )}
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="border-b border-slate-200/80 dark:border-slate-800/80 bg-slate-50/70 dark:bg-slate-950/40 text-[11px] font-mono font-semibold uppercase tracking-wider text-slate-400">
                  <th className="py-3 px-4 sm:px-5">Server Title / Name</th>
                  <th className="py-3 px-4">IP Address & Port</th>
                  <th className="py-3 px-4">Region / Zone</th>
                  <th className="py-3 px-4">Status</th>
                  <th className="py-3 px-4 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-slate-800/60 text-sm">
                {filteredServers.map((server) => {
                  const isOnline = server.status === 'ONLINE';
                  const isCopied = copiedId === server.server_id;

                  return (
                    <tr
                      key={server.server_id}
                      className="hover:bg-slate-50/80 dark:hover:bg-slate-800/40 transition-colors group"
                    >
                      {/* Server Title / Name (Distinct Column) */}
                      <td className="py-3.5 px-4 sm:px-5">
                        <div className="flex items-center gap-3">
                          <div
                            className={`w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0 ${
                              isOnline
                                ? 'bg-cyan-500/10 text-cyan-600 dark:text-cyan-400 border border-cyan-500/20'
                                : 'bg-slate-800 text-slate-400 border border-slate-700/50'
                            }`}
                          >
                            <Server className="w-4 h-4" />
                          </div>
                          <div>
                            <div className="font-semibold text-slate-900 dark:text-slate-100 line-clamp-1 group-hover:text-cyan-500 transition-colors">
                              {server.server_name}
                            </div>
                            {server.player_count !== undefined && server.max_players && (
                              <span className="text-[11px] font-mono text-slate-400">
                                Players: {server.player_count}/{server.max_players}
                              </span>
                            )}
                          </div>
                        </div>
                      </td>

                      {/* IP & Port (Distinct Column with Copy Button) */}
                      <td className="py-3.5 px-4">
                        <div className="inline-flex items-center gap-1.5 bg-slate-100 dark:bg-slate-950/80 px-2.5 py-1 rounded-lg border border-slate-200 dark:border-slate-800 text-xs font-mono">
                          <span className="text-cyan-700 dark:text-cyan-300 font-medium">
                            {server.server_id}
                          </span>
                          <button
                            type="button"
                            title="Copy IP:Port to clipboard"
                            onClick={() => handleCopyIp(server.server_id)}
                            className="text-slate-400 hover:text-cyan-500 transition-colors p-0.5 rounded cursor-pointer"
                          >
                            {isCopied ? (
                              <Check className="w-3.5 h-3.5 text-emerald-500" />
                            ) : (
                              <Copy className="w-3.5 h-3.5" />
                            )}
                          </button>
                        </div>
                      </td>

                      {/* Region / Zone (Distinct Column) */}
                      <td className="py-3.5 px-4">
                        <Badge variant="neutral" size="sm" className="font-medium text-xs">
                          <MapPin className="w-3 h-3 text-slate-400" />
                          {server.region || 'Unknown'}
                        </Badge>
                      </td>

                      {/* Status */}
                      <td className="py-3.5 px-4">
                        <Badge
                          variant={isOnline ? 'emerald' : 'rose'}
                          size="sm"
                          dot
                          pulse={isOnline}
                          className="text-[11px]"
                        >
                          {server.status || 'UNKNOWN'}
                        </Badge>
                      </td>

                      {/* Actions */}
                      <td className="py-3.5 px-4 text-right">
                        <div className="flex items-center justify-end gap-1.5">
                          <Button
                            variant="outline"
                            size="sm"
                            icon={Pencil}
                            onClick={() => handleOpenEdit(server)}
                            className="h-8 px-2.5 text-xs text-slate-600 dark:text-slate-300 hover:text-cyan-500"
                          >
                            Edit
                          </Button>
                          <Button
                            variant="danger"
                            size="sm"
                            icon={Trash2}
                            onClick={() => setDeletingServer(server)}
                            className="h-8 px-2.5 text-xs"
                          >
                            Delete
                          </Button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {/* ========================================================================= */}
      {/* 1. ADD SERVER MODAL (Closed by default, opens on clicking Add New Server)  */}
      {/* ========================================================================= */}
      <Modal
        isOpen={isAddModalOpen}
        onClose={() => !isSubmittingAdd && setIsAddModalOpen(false)}
        title="Register New Monitored Server"
        subtitle="Provide node connection telemetry and assign target monitoring region."
        maxWidth="max-w-lg"
      >
        <form onSubmit={handleAddSubmit} className="space-y-4 pt-1">
          {/* IP & Port Fields */}
          <div>
            <label className="block text-xs font-mono text-slate-600 dark:text-slate-400 mb-1.5 uppercase tracking-wider">
              Server Network Address (IP & Port)
            </label>
            <div className="grid grid-cols-3 gap-2">
              <div className="col-span-2">
                <Input
                  type="text"
                  placeholder="e.g. 54.36.173.60"
                  value={addIp}
                  onChange={(e) => handleAddIpChange(e.target.value)}
                  disabled={isSubmittingAdd}
                  required
                />
              </div>
              <div>
                <Input
                  type="text"
                  placeholder="Port (27015)"
                  value={addPort}
                  onChange={(e) => setAddPort(e.target.value)}
                  disabled={isSubmittingAdd}
                  required
                />
              </div>
            </div>
            <p className="text-[11px] text-slate-400 mt-1">
              You can also paste a full <code className="font-mono text-cyan-400">IP:Port</code> address into the first box.
            </p>
          </div>

          {/* Server Name Field */}
          <div>
            <label className="block text-xs font-mono text-slate-600 dark:text-slate-400 mb-1.5 uppercase tracking-wider">
              Server Display Name
            </label>
            <Input
              type="text"
              placeholder="e.g. CS2 5v5 Polish Server #1"
              value={addName}
              onChange={(e) => setAddName(e.target.value)}
              disabled={isSubmittingAdd}
              required
            />
          </div>

          {/* Region Selector (Dropdown options) */}
          <div>
            <label className="block text-xs font-mono text-slate-600 dark:text-slate-400 mb-1.5 uppercase tracking-wider">
              Target Hosting Region
            </label>
            <select
              value={addRegion}
              onChange={(e) => setAddRegion(e.target.value)}
              disabled={isSubmittingAdd}
              className="w-full bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700/80 rounded-lg px-3 py-2 text-sm text-slate-900 dark:text-slate-100 outline-none focus:border-cyan-500 font-sans cursor-pointer"
            >
              {availableRegions.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          </div>

          {/* Custom Region Input if '__custom__' selected */}
          {addRegion === '__custom__' && (
            <div className="animate-fade-in">
              <label className="block text-xs font-mono text-cyan-600 dark:text-cyan-400 mb-1.5 uppercase tracking-wider">
                Specify Custom Region Name
              </label>
              <Input
                type="text"
                placeholder="e.g. Frankfurt-DC2 or Dubai"
                value={addCustomRegion}
                onChange={(e) => setAddCustomRegion(e.target.value)}
                disabled={isSubmittingAdd}
                required
              />
            </div>
          )}

          {/* Action Buttons */}
          <div className="flex items-center justify-end gap-3 pt-3 border-t border-slate-100 dark:border-slate-800">
            <Button
              type="button"
              variant="ghost"
              onClick={() => setIsAddModalOpen(false)}
              disabled={isSubmittingAdd}
            >
              Cancel
            </Button>
            <Button
              type="submit"
              variant="primary"
              loading={isSubmittingAdd}
              disabled={isSubmittingAdd}
            >
              Add Monitored Server
            </Button>
          </div>
        </form>
      </Modal>

      {/* ========================================================================= */}
      {/* 2. EDIT SERVER MODAL (Replaces browser prompt)                            */}
      {/* ========================================================================= */}
      <Modal
        isOpen={Boolean(editingServer)}
        onClose={() => !isSubmittingEdit && setEditingServer(null)}
        title="Edit Monitored Server"
        subtitle={editingServer ? `Target ID: ${editingServer.server_id}` : ''}
        maxWidth="max-w-lg"
      >
        {editingServer && (
          <form onSubmit={handleEditSubmit} className="space-y-4 pt-1">
            <div>
              <label className="block text-xs font-mono text-slate-600 dark:text-slate-400 mb-1.5 uppercase tracking-wider">
                Server IP:Port Address
              </label>
              <Input
                type="text"
                value={editingServer.server_id}
                disabled
                className="opacity-70 bg-slate-100 dark:bg-slate-800/60 font-mono text-slate-400"
              />
              <p className="text-[11px] text-slate-400 mt-1">
                Node ID / Network address is the primary telemetry key.
              </p>
            </div>

            <div>
              <label className="block text-xs font-mono text-slate-600 dark:text-slate-400 mb-1.5 uppercase tracking-wider">
                Server Display Name
              </label>
              <Input
                type="text"
                value={editName}
                onChange={(e) => setEditName(e.target.value)}
                disabled={isSubmittingEdit}
                required
              />
            </div>

            <div>
              <label className="block text-xs font-mono text-slate-600 dark:text-slate-400 mb-1.5 uppercase tracking-wider">
                Target Hosting Region
              </label>
              <select
                value={editRegion}
                onChange={(e) => setEditRegion(e.target.value)}
                disabled={isSubmittingEdit}
                className="w-full bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700/80 rounded-lg px-3 py-2 text-sm text-slate-900 dark:text-slate-100 outline-none focus:border-cyan-500 font-sans cursor-pointer"
              >
                {availableRegions.map((opt) => (
                  <option key={opt.value} value={opt.value}>
                    {opt.label}
                  </option>
                ))}
              </select>
            </div>

            {editRegion === '__custom__' && (
              <div className="animate-fade-in">
                <label className="block text-xs font-mono text-cyan-600 dark:text-cyan-400 mb-1.5 uppercase tracking-wider">
                  Specify Custom Region Name
                </label>
                <Input
                  type="text"
                  placeholder="e.g. Frankfurt-DC2"
                  value={editCustomRegion}
                  onChange={(e) => setEditCustomRegion(e.target.value)}
                  disabled={isSubmittingEdit}
                  required
                />
              </div>
            )}

            <div className="flex items-center justify-end gap-3 pt-3 border-t border-slate-100 dark:border-slate-800">
              <Button
                type="button"
                variant="ghost"
                onClick={() => setEditingServer(null)}
                disabled={isSubmittingEdit}
              >
                Cancel
              </Button>
              <Button
                type="submit"
                variant="primary"
                loading={isSubmittingEdit}
                disabled={isSubmittingEdit}
              >
                Save Changes
              </Button>
            </div>
          </form>
        )}
      </Modal>

      {/* ========================================================================= */}
      {/* 3. DELETE SERVER CONFIRMATION MODAL (Replaces browser confirm)            */}
      {/* ========================================================================= */}
      <Modal
        isOpen={Boolean(deletingServer)}
        onClose={() => !isSubmittingDelete && setDeletingServer(null)}
        title="Remove Server from Monitoring"
        subtitle="This action will delete telemetry collection for this node."
        maxWidth="max-w-md"
      >
        {deletingServer && (
          <div className="space-y-4 pt-1">
            <div className="p-3.5 rounded-xl bg-rose-50 dark:bg-rose-500/10 border border-rose-200 dark:border-rose-500/30 text-rose-700 dark:text-rose-400 text-xs flex items-start gap-3">
              <AlertCircle className="w-5 h-5 flex-shrink-0 mt-0.5" />
              <div>
                <p className="font-semibold text-rose-800 dark:text-rose-300">
                  Are you sure you want to delete this node?
                </p>
                <p className="mt-1 text-slate-600 dark:text-slate-300">
                  The A2S poller will immediately halt ping and status tracking for this server.
                </p>
              </div>
            </div>

            <div className="p-3 rounded-lg bg-slate-100 dark:bg-slate-950/60 border border-slate-200 dark:border-slate-800 font-mono text-xs space-y-1.5">
              <div className="text-slate-900 dark:text-slate-100 font-semibold">
                {deletingServer.server_name}
              </div>
              <div className="text-cyan-600 dark:text-cyan-400">
                {deletingServer.server_id}
              </div>
              <div className="text-slate-400">
                Region: {deletingServer.region}
              </div>
            </div>

            <div className="flex items-center justify-end gap-3 pt-3 border-t border-slate-100 dark:border-slate-800">
              <Button
                type="button"
                variant="ghost"
                onClick={() => setDeletingServer(null)}
                disabled={isSubmittingDelete}
              >
                Cancel
              </Button>
              <Button
                type="button"
                variant="danger"
                loading={isSubmittingDelete}
                onClick={handleDeleteSubmit}
                disabled={isSubmittingDelete}
              >
                Delete Server
              </Button>
            </div>
          </div>
        )}
      </Modal>
    </div>
  );
}

