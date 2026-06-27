import { useEffect, useState } from 'react';
import { api } from '../lib/api';
import { Activity, Users, Key, FileText } from 'lucide-react';

function StatCard({ icon: Icon, label, value, color }: { icon: any; label: string; value: string | number; color: string }) {
  return (
    <div className="bg-bg-card rounded-xl p-5 border border-slate-700">
      <div className="flex items-center gap-3 mb-2">
        <Icon size={20} className={color} />
        <span className="text-slate-400 text-sm">{label}</span>
      </div>
      <p className="text-2xl font-bold text-white">{value}</p>
    </div>
  );
}

export default function DashboardPage() {
  const [health, setHealth] = useState<any>(null);
  const [accounts, setAccounts] = useState<any[]>([]);
  const [keys, setKeys] = useState<any[]>([]);
  const [logs, setLogs] = useState<any[]>([]);

  useEffect(() => {
    api.health().then(setHealth).catch(() => {});
    api.accounts.list().then(setAccounts).catch(() => {});
    api.keys.list().then(setKeys).catch(() => {});
    api.logs.list({ limit: '10' }).then(setLogs).catch(() => {});
  }, []);

  const activeKeys = keys.filter(k => k.is_active).length;
  const activeAccounts = accounts.filter(a => a.status === 'active').length;
  const onlineServers = health?.servers?.filter((s: any) => s.status === 'online').length || 0;
  const totalServers = health?.servers?.length || 4;

  return (
    <div>
      <h2 className="text-2xl font-bold text-white mb-6">Dashboard</h2>
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        <StatCard icon={Activity} label="Servidores SAT" value={`${onlineServers}/${totalServers}`} color="text-green-400" />
        <StatCard icon={Users} label="Cuentas activas" value={activeAccounts} color="text-blue-400" />
        <StatCard icon={Key} label="API Keys activas" value={activeKeys} color="text-purple-400" />
        <StatCard icon={FileText} label="Operaciones hoy" value={logs.length} color="text-amber-400" />
      </div>

      <div className="bg-bg-card rounded-xl border border-slate-700 p-5">
        <h3 className="text-lg font-semibold text-white mb-4">Actividad reciente</h3>
        {logs.length === 0 ? (
          <p className="text-slate-400 text-sm">Sin actividad reciente</p>
        ) : (
          <div className="space-y-2">
            {logs.map((log: any) => (
              <div key={log.id} className="flex items-center justify-between py-2 border-b border-slate-700/50 last:border-0">
                <div>
                  <span className="text-white text-sm font-mono">{log.action}</span>
                  {log.account_nit && <span className="text-slate-400 text-xs ml-2">NIT: {log.account_nit}</span>}
                </div>
                <div className="flex items-center gap-3">
                  <span className={`text-xs px-2 py-0.5 rounded ${log.response_status < 300 ? 'bg-green-900/30 text-green-400' : 'bg-red-900/30 text-red-400'}`}>
                    {log.response_status}
                  </span>
                  <span className="text-slate-500 text-xs">{log.duration_ms}ms</span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
