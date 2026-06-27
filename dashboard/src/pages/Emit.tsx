import { useEffect, useState } from 'react';
import { api } from '../lib/api';
import { Send, Search } from 'lucide-react';

export default function Emit() {
  const [accounts, setAccounts] = useState<any[]>([]);
  const [form, setForm] = useState({
    account_nit: '', tipo: 'FACT', receptor_nit: 'CF', receptor_nombre: 'Consumidor Final',
    descripcion: '', cantidad: '1', precio: '',
  });
  const [nitInfo, setNitInfo] = useState('');
  const [result, setResult] = useState<any>(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  useEffect(() => { api.accounts.list().then(setAccounts).catch(() => {}); }, []);

  async function lookupNit() {
    if (!form.account_nit || !form.receptor_nit) return;
    try {
      const res = await api.nit.lookup(form.account_nit, form.receptor_nit);
      setNitInfo(res.nombre);
      setForm({ ...form, receptor_nombre: res.nombre });
    } catch (err: any) {
      setNitInfo(`Error: ${err.message}`);
    }
  }

  async function emit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError('');
    setResult(null);
    try {
      const precio = parseFloat(form.precio);
      const cantidad = parseInt(form.cantidad);
      const res = await api.dte.emit({
        account_nit: form.account_nit,
        tipo: form.tipo,
        receptor_nit: form.receptor_nit,
        receptor_nombre: form.receptor_nombre,
        items: [{
          descripcion: form.descripcion,
          cantidad,
          precio_unitario: precio,
          descuento: 0,
        }],
      });
      setResult(res);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div>
      <h2 className="text-2xl font-bold text-white mb-6">Emitir DTE</h2>
      <form onSubmit={emit} className="bg-bg-card rounded-xl border border-slate-700 p-6 space-y-4 max-w-2xl">
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="text-slate-400 text-xs block mb-1">Cuenta emisora</label>
            <select value={form.account_nit} onChange={e => setForm({ ...form, account_nit: e.target.value })} className="w-full px-3 py-2 bg-slate-800 border border-slate-600 rounded-lg text-white text-sm" required>
              <option value="">Seleccionar...</option>
              {accounts.filter(a => a.status === 'active').map(a => (
                <option key={a.nit} value={a.nit}>{a.nit} — {a.name || a.affiliation}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="text-slate-400 text-xs block mb-1">Tipo DTE</label>
            <select value={form.tipo} onChange={e => setForm({ ...form, tipo: e.target.value })} className="w-full px-3 py-2 bg-slate-800 border border-slate-600 rounded-lg text-white text-sm">
              <option value="FACT">FACT — Factura</option>
              <option value="FCAM">FCAM — Cambiaria</option>
              <option value="FPEQ">FPEQ — Pequeño contribuyente</option>
              <option value="FESP">FESP — Especial</option>
              <option value="NABN">NABN — Abono</option>
              <option value="NDEB">NDEB — Nota débito</option>
              <option value="NCRE">NCRE — Nota crédito</option>
            </select>
          </div>
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="text-slate-400 text-xs block mb-1">NIT Receptor</label>
            <div className="flex gap-2">
              <input value={form.receptor_nit} onChange={e => setForm({ ...form, receptor_nit: e.target.value })} className="flex-1 px-3 py-2 bg-slate-800 border border-slate-600 rounded-lg text-white text-sm" />
              <button type="button" onClick={lookupNit} className="px-3 py-2 bg-slate-700 hover:bg-slate-600 rounded-lg text-white cursor-pointer" title="Buscar NIT">
                <Search size={16} />
              </button>
            </div>
            {nitInfo && <p className="text-xs mt-1 text-slate-400">{nitInfo}</p>}
          </div>
          <div>
            <label className="text-slate-400 text-xs block mb-1">Nombre Receptor</label>
            <input value={form.receptor_nombre} onChange={e => setForm({ ...form, receptor_nombre: e.target.value })} className="w-full px-3 py-2 bg-slate-800 border border-slate-600 rounded-lg text-white text-sm" />
          </div>
        </div>

        <div>
          <label className="text-slate-400 text-xs block mb-1">Descripción</label>
          <input value={form.descripcion} onChange={e => setForm({ ...form, descripcion: e.target.value })} placeholder="Servicio profesional..." className="w-full px-3 py-2 bg-slate-800 border border-slate-600 rounded-lg text-white text-sm" required />
        </div>
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="text-slate-400 text-xs block mb-1">Cantidad</label>
            <input type="number" value={form.cantidad} onChange={e => setForm({ ...form, cantidad: e.target.value })} min="1" className="w-full px-3 py-2 bg-slate-800 border border-slate-600 rounded-lg text-white text-sm" />
          </div>
          <div>
            <label className="text-slate-400 text-xs block mb-1">Precio unitario (Q)</label>
            <input type="number" step="0.01" value={form.precio} onChange={e => setForm({ ...form, precio: e.target.value })} placeholder="100.00" className="w-full px-3 py-2 bg-slate-800 border border-slate-600 rounded-lg text-white text-sm" required />
          </div>
        </div>

        {error && <p className="text-red-400 text-sm">{error}</p>}

        <button type="submit" disabled={loading} className="flex items-center gap-2 px-6 py-3 bg-accent hover:bg-accent-hover text-white rounded-lg font-medium disabled:opacity-50 cursor-pointer">
          <Send size={16} />
          {loading ? 'Emitiendo...' : 'Emitir factura'}
        </button>
      </form>

      {result && (
        <div className="mt-6 bg-green-900/20 border border-green-700 rounded-xl p-5 max-w-2xl">
          <h3 className="text-green-400 font-semibold mb-3">DTE certificado</h3>
          <div className="grid grid-cols-2 gap-2 text-sm">
            <div><span className="text-slate-400">UUID:</span> <span className="text-white font-mono">{result.uuid}</span></div>
            <div><span className="text-slate-400">Serie:</span> <span className="text-white">{result.serie}</span></div>
            <div><span className="text-slate-400">Número:</span> <span className="text-white">{result.numero}</span></div>
            <div><span className="text-slate-400">Vía:</span> <span className="text-white">{result.source}</span></div>
          </div>
        </div>
      )}
    </div>
  );
}
