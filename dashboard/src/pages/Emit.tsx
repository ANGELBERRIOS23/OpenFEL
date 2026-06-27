import { useEffect, useState } from 'react';
import { api } from '../lib/api';
import { Send, Search, Plus, Trash2 } from 'lucide-react';
import { useTheme } from '../lib/useThemeClasses';

interface LineItem {
  descripcion: string;
  cantidad: string;
  precio: string;
}

export default function Emit() {
  const t = useTheme();
  const [accounts, setAccounts] = useState<any[]>([]);
  const [accountNit, setAccountNit] = useState('');
  const [tipo, setTipo] = useState('FACT');
  const [receptorNit, setReceptorNit] = useState('CF');
  const [receptorNombre, setReceptorNombre] = useState('Consumidor Final');
  const [items, setItems] = useState<LineItem[]>([{ descripcion: '', cantidad: '1', precio: '' }]);
  const [nitInfo, setNitInfo] = useState('');
  const [result, setResult] = useState<any>(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  useEffect(() => { api.accounts.list().then(setAccounts).catch(() => {}); }, []);

  async function lookupNit() {
    if (!accountNit || !receptorNit) return;
    try {
      const res = await api.nit.lookup(accountNit, receptorNit);
      setNitInfo(res.nombre);
      setReceptorNombre(res.nombre);
    } catch (err: any) {
      setNitInfo(`Error: ${err.message}`);
    }
  }

  function updateItem(i: number, field: keyof LineItem, value: string) {
    setItems(prev => prev.map((item, idx) => idx === i ? { ...item, [field]: value } : item));
  }

  function addItem() {
    setItems(prev => [...prev, { descripcion: '', cantidad: '1', precio: '' }]);
  }

  function removeItem(i: number) {
    if (items.length <= 1) return;
    setItems(prev => prev.filter((_, idx) => idx !== i));
  }

  const total = items.reduce((sum, item) => sum + (parseFloat(item.precio) || 0) * (parseInt(item.cantidad) || 0), 0);

  async function emit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError('');
    setResult(null);
    try {
      const res = await api.dte.emit({
        account_nit: accountNit,
        tipo,
        receptor_nit: receptorNit,
        receptor_nombre: receptorNombre,
        items: items.map(item => ({
          descripcion: item.descripcion,
          cantidad: parseInt(item.cantidad),
          precio_unitario: parseFloat(item.precio),
          descuento: 0,
        })),
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
      <h2 className={`text-xl sm:text-2xl font-bold ${t.textH} mb-6`}>Emitir DTE</h2>
      <form onSubmit={emit} className={`rounded-xl border p-4 sm:p-6 space-y-4 max-w-3xl ${t.card}`}>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <label className={`${t.textMuted} text-xs block mb-1`}>Cuenta emisora</label>
            <select value={accountNit} onChange={e => setAccountNit(e.target.value)} className={`w-full px-3 py-2 border rounded-lg text-sm ${t.input}`} required>
              <option value="">Seleccionar...</option>
              {accounts.filter(a => a.status === 'active').map(a => (
                <option key={a.nit} value={a.nit}>{a.nit} — {a.name || a.affiliation}</option>
              ))}
            </select>
          </div>
          <div>
            <label className={`${t.textMuted} text-xs block mb-1`}>Tipo DTE</label>
            <select value={tipo} onChange={e => setTipo(e.target.value)} className={`w-full px-3 py-2 border rounded-lg text-sm ${t.input}`}>
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

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <label className={`${t.textMuted} text-xs block mb-1`}>NIT Receptor</label>
            <div className="flex gap-2">
              <input value={receptorNit} onChange={e => setReceptorNit(e.target.value)} className={`flex-1 px-3 py-2 border rounded-lg text-sm ${t.input}`} />
              <button type="button" onClick={lookupNit} className={`px-3 py-2 rounded-lg cursor-pointer ${t.btnSecondary}`} title="Buscar NIT">
                <Search size={16} />
              </button>
            </div>
            {nitInfo && <p className={`text-xs mt-1 ${t.textMuted}`}>{nitInfo}</p>}
          </div>
          <div>
            <label className={`${t.textMuted} text-xs block mb-1`}>Nombre Receptor</label>
            <input value={receptorNombre} onChange={e => setReceptorNombre(e.target.value)} className={`w-full px-3 py-2 border rounded-lg text-sm ${t.input}`} />
          </div>
        </div>

        {/* Line items */}
        <div>
          <div className="flex items-center justify-between mb-2">
            <label className={`${t.textMuted} text-xs`}>Servicios / Productos</label>
            <button type="button" onClick={addItem} className="flex items-center gap-1 text-accent text-xs cursor-pointer hover:underline">
              <Plus size={14} /> Agregar línea
            </button>
          </div>
          <div className="space-y-3">
            {items.map((item, i) => (
              <div key={i} className={`grid grid-cols-1 sm:grid-cols-[1fr_80px_120px_32px] gap-2 items-end p-3 rounded-lg border ${t.borderSub} ${t.isDark ? 'bg-slate-800/50' : 'bg-slate-50'}`}>
                <div>
                  {i === 0 && <label className={`${t.textXs} text-xs block mb-1`}>Descripción</label>}
                  <input value={item.descripcion} onChange={e => updateItem(i, 'descripcion', e.target.value)} placeholder="Servicio profesional..." className={`w-full px-3 py-2 border rounded-lg text-sm ${t.input}`} required />
                </div>
                <div>
                  {i === 0 && <label className={`${t.textXs} text-xs block mb-1`}>Cant.</label>}
                  <input type="number" value={item.cantidad} onChange={e => updateItem(i, 'cantidad', e.target.value)} min="1" className={`w-full px-3 py-2 border rounded-lg text-sm ${t.input}`} />
                </div>
                <div>
                  {i === 0 && <label className={`${t.textXs} text-xs block mb-1`}>Precio (Q)</label>}
                  <input type="number" step="0.01" value={item.precio} onChange={e => updateItem(i, 'precio', e.target.value)} placeholder="100.00" className={`w-full px-3 py-2 border rounded-lg text-sm ${t.input}`} required />
                </div>
                <button type="button" onClick={() => removeItem(i)} disabled={items.length <= 1} className={`p-2 ${t.textMuted} hover:text-red-400 cursor-pointer disabled:opacity-30`}>
                  <Trash2 size={16} />
                </button>
              </div>
            ))}
          </div>
          <div className={`text-right mt-2 text-sm ${t.textH} font-semibold`}>Total: Q{total.toFixed(2)}</div>
        </div>

        {error && <p className="text-red-400 text-sm">{error}</p>}

        <button type="submit" disabled={loading} className="flex items-center gap-2 px-6 py-3 bg-accent hover:bg-accent-hover text-white rounded-lg font-medium disabled:opacity-50 cursor-pointer">
          <Send size={16} />
          {loading ? 'Emitiendo...' : 'Emitir factura'}
        </button>
      </form>

      {result && (
        <div className="mt-6 bg-green-900/20 border border-green-700 rounded-xl p-4 sm:p-5 max-w-3xl">
          <h3 className="text-green-400 font-semibold mb-3">DTE certificado</h3>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-sm">
            <div><span className={t.textMuted}>UUID:</span> <span className={`${t.textH} font-mono text-xs`}>{result.uuid}</span></div>
            <div><span className={t.textMuted}>Serie:</span> <span className={t.textH}>{result.serie}</span></div>
            <div><span className={t.textMuted}>Número:</span> <span className={t.textH}>{result.numero}</span></div>
            <div><span className={t.textMuted}>Vía:</span> <span className={t.textH}>{result.source}</span></div>
          </div>
        </div>
      )}
    </div>
  );
}
