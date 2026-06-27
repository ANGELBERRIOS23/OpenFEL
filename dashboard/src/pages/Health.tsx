import { useEffect, useState } from 'react';
import { api } from '../lib/api';
import { RefreshCw, Wifi, WifiOff } from 'lucide-react';

export default function Health() {
  const [health, setHealth] = useState<any>(null);
  const [loading, setLoading] = useState(false);

  async function load() {
    setLoading(true);
    try {
      setHealth(await api.health());
    } catch {
      setHealth(null);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, []);

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-2xl font-bold text-white">Estado Servidores SAT</h2>
        <button onClick={load} disabled={loading} className="flex items-center gap-2 px-4 py-2 bg-slate-700 hover:bg-slate-600 text-white rounded-lg text-sm disabled:opacity-50 cursor-pointer">
          <RefreshCw size={16} className={loading ? 'animate-spin' : ''} /> Actualizar
        </button>
      </div>

      {health && (
        <div className="mb-6">
          <span className={`inline-flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-semibold ${
            health.overall === 'healthy' ? 'bg-green-900/30 text-green-400 border border-green-700' :
            health.overall === 'degraded' ? 'bg-amber-900/30 text-amber-400 border border-amber-700' :
            'bg-red-900/30 text-red-400 border border-red-700'
          }`}>
            {health.overall === 'healthy' ? <Wifi size={16} /> : <WifiOff size={16} />}
            {health.overall.toUpperCase()}
          </span>
          <span className="text-slate-500 text-xs ml-3">{health.timestamp}</span>
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {(health?.servers || []).map((s: any, i: number) => (
          <div key={i} className="bg-bg-card rounded-xl border border-slate-700 p-5">
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-white font-semibold">{s.server}</h3>
              <span className={`px-2 py-0.5 rounded text-xs ${s.status === 'online' ? 'bg-green-900/30 text-green-400' : 'bg-red-900/30 text-red-400'}`}>
                {s.status}
              </span>
            </div>
            <div className="space-y-1 text-sm">
              <div className="flex justify-between"><span className="text-slate-400">Dominio</span><span className="text-slate-300 font-mono text-xs">{s.domain}</span></div>
              {s.ip && <div className="flex justify-between"><span className="text-slate-400">IP</span><span className="text-slate-300 font-mono text-xs">{s.ip}</span></div>}
              <div className="flex justify-between"><span className="text-slate-400">DNS</span><span className={s.dns ? 'text-green-400' : 'text-red-400'}>{s.dns ? 'OK' : 'FAIL'}</span></div>
              <div className="flex justify-between"><span className="text-slate-400">TLS</span><span className={s.tls ? 'text-green-400' : 'text-red-400'}>{s.tls ? 'OK' : 'FAIL'}</span></div>
              <div className="flex justify-between"><span className="text-slate-400">HTTP</span><span className={s.http ? 'text-green-400' : 'text-red-400'}>{s.http ? 'OK' : 'FAIL'}</span></div>
              {s.latency_ms != null && <div className="flex justify-between"><span className="text-slate-400">Latencia</span><span className="text-slate-300">{s.latency_ms}ms</span></div>}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
