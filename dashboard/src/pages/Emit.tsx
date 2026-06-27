import { useEffect, useState } from 'react';
import { api } from '../lib/api';
import { Send, Search, Plus, Trash2, UserX, Info } from 'lucide-react';
import { useTheme } from '../lib/useThemeClasses';

const TAX_REGIMES = [
  { value: 'GENERAL', label: 'General (IVA 12%)' },
  { value: 'EXENTO', label: 'Exento de IVA' },
  { value: 'EXPORT', label: 'Exportación' },
  { value: 'PEQ', label: 'Pequeño contribuyente' },
  { value: 'NO_AFECTO', label: 'No afecto' },
  { value: 'TURISMO_HOSPEDAJE', label: 'Turismo / Hospedaje (10%)' },
];

const DTE_TYPES = [
  { value: 'FACT', label: 'FACT — Factura', gen: true },
  { value: 'FCAM', label: 'FCAM — Factura cambiaria', gen: true },
  { value: 'FPEQ', label: 'FPEQ — Pequeño contribuyente', gen: false },
  { value: 'FESP', label: 'FESP — Factura especial', gen: true },
  { value: 'NABN', label: 'NABN — Nota de abono', gen: true },
  { value: 'NDEB', label: 'NDEB — Nota de débito', gen: true },
  { value: 'NCRE', label: 'NCRE — Nota de crédito', gen: true },
];

const FRASE_MAP: Record<string, { tipo: number; escenario: number; label: string }[]> = {
  'FACT-GENERAL': [{ tipo: 1, escenario: 1, label: 'IVA General' }],
  'FACT-EXENTO': [{ tipo: 1, escenario: 1, label: 'IVA General' }, { tipo: 4, escenario: 3, label: 'Exento' }],
  'FACT-EXPORT': [{ tipo: 1, escenario: 2, label: 'Exportación GEN' }, { tipo: 4, escenario: 1, label: 'Exportación' }],
  'FACT-TURISMO_HOSPEDAJE': [{ tipo: 1, escenario: 1, label: 'IVA General' }, { tipo: 4, escenario: 7, label: 'Turismo/Hospedaje' }],
  'FACT-NO_AFECTO': [{ tipo: 1, escenario: 1, label: 'IVA General' }],
  'FCAM-GENERAL': [{ tipo: 1, escenario: 1, label: 'IVA General' }],
  'FCAM-EXPORT': [{ tipo: 1, escenario: 2, label: 'Exportación GEN' }, { tipo: 4, escenario: 1, label: 'Exportación' }],
  'FESP-GENERAL': [],
  'FPEQ-PEQ': [{ tipo: 3, escenario: 1, label: 'PEQ' }],
  'NABN-GENERAL': [],
  'NDEB-GENERAL': [{ tipo: 1, escenario: 1, label: 'IVA General' }],
  'NCRE-GENERAL': [{ tipo: 1, escenario: 1, label: 'IVA General' }],
};

interface LineItem {
  descripcion: string;
  cantidad: string;
  precio: string;
  descuento: string;
  regimen: string;
}

export default function Emit() {
  const t = useTheme();
  const [accounts, setAccounts] = useState<any[]>([]);
  const [accountNit, setAccountNit] = useState('');
  const [tipo, setTipo] = useState('FACT');
  const [receptorNit, setReceptorNit] = useState('CF');
  const [receptorNombre, setReceptorNombre] = useState('Consumidor Final');
  const [items, setItems] = useState<LineItem[]>([{ descripcion: '', cantidad: '1', precio: '', descuento: '0', regimen: 'GENERAL' }]);
  const [nitInfo, setNitInfo] = useState('');
  const [result, setResult] = useState<any>(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [lookingUp, setLookingUp] = useState(false);

  useEffect(() => { api.accounts.list().then(setAccounts).catch(() => {}); }, []);

  const selectedAccount = accounts.find(a => a.nit === accountNit);
  const isPEQ = selectedAccount?.affiliation === 'PEQ';

  useEffect(() => {
    if (isPEQ && tipo !== 'FPEQ') setTipo('FPEQ');
    if (isPEQ) {
      setItems(prev => prev.map(it => ({ ...it, regimen: 'PEQ' })));
    }
  }, [accountNit]);

  const primaryRegimen = items[0]?.regimen || 'GENERAL';
  const fraseKey = `${tipo}-${primaryRegimen}`;
  const frases = FRASE_MAP[fraseKey] || FRASE_MAP[`${tipo}-GENERAL`] || [];

  async function lookupNit() {
    if (!accountNit || !receptorNit) return;
    setLookingUp(true);
    try {
      const res = await api.nit.lookup(accountNit, receptorNit);
      setNitInfo(res.nombre);
      setReceptorNombre(res.nombre);
    } catch (err: any) {
      setNitInfo(`Error: ${err.message}`);
    } finally {
      setLookingUp(false);
    }
  }

  function setCF() {
    setReceptorNit('CF');
    setReceptorNombre('Consumidor Final');
    setNitInfo('');
  }

  function updateItem(i: number, field: keyof LineItem, value: string) {
    setItems(prev => prev.map((item, idx) => idx === i ? { ...item, [field]: value } : item));
  }

  function addItem() {
    setItems(prev => [...prev, { descripcion: '', cantidad: '1', precio: '', descuento: '0', regimen: isPEQ ? 'PEQ' : 'GENERAL' }]);
  }

  function removeItem(i: number) {
    if (items.length <= 1) return;
    setItems(prev => prev.filter((_, idx) => idx !== i));
  }

  const subtotal = items.reduce((sum, item) => {
    const qty = parseInt(item.cantidad) || 0;
    const price = parseFloat(item.precio) || 0;
    const desc = parseFloat(item.descuento) || 0;
    return sum + (qty * price) - desc;
  }, 0);

  const totalDescuentos = items.reduce((sum, item) => sum + (parseFloat(item.descuento) || 0), 0);

  async function emit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError('');
    setResult(null);
    try {
      const isExport = items.some(it => it.regimen === 'EXPORT');
      const res = await api.dte.emit({
        account_nit: accountNit,
        tipo,
        receptor_nit: receptorNit,
        receptor_nombre: receptorNombre,
        export: isExport,
        items: items.map(item => ({
          descripcion: item.descripcion,
          cantidad: parseInt(item.cantidad),
          precio_unitario: parseFloat(item.precio),
          descuento: parseFloat(item.descuento) || 0,
          regimen: item.regimen,
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
      <form onSubmit={emit} className={`rounded-xl border p-4 sm:p-6 space-y-5 max-w-4xl ${t.card}`}>
        {/* Account + tipo */}
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
              {DTE_TYPES.filter(d => isPEQ ? !d.gen : d.gen).map(d => (
                <option key={d.value} value={d.value}>{d.label}</option>
              ))}
            </select>
          </div>
        </div>

        {/* Receptor */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <label className={`${t.textMuted} text-xs block mb-1`}>NIT Receptor</label>
            <div className="flex gap-2">
              <input value={receptorNit} onChange={e => setReceptorNit(e.target.value)} className={`flex-1 px-3 py-2 border rounded-lg text-sm ${t.input}`} />
              <button type="button" onClick={setCF} className={`px-3 py-2 rounded-lg cursor-pointer text-xs font-semibold ${receptorNit === 'CF' ? 'bg-accent text-white' : t.btnSecondary}`} title="Consumidor Final">
                <UserX size={16} />
              </button>
              <button type="button" onClick={lookupNit} disabled={lookingUp || !accountNit} className={`px-3 py-2 rounded-lg cursor-pointer ${t.btnSecondary} disabled:opacity-50`} title="Buscar NIT en SAT">
                <Search size={16} />
              </button>
            </div>
            {nitInfo && <p className={`text-xs mt-1 ${nitInfo.startsWith('Error') ? 'text-red-400' : t.textMuted}`}>{nitInfo}</p>}
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
              <div key={i} className={`p-3 rounded-lg border ${t.borderSub} ${t.isDark ? 'bg-slate-800/50' : 'bg-slate-50'}`}>
                <div className="grid grid-cols-1 sm:grid-cols-[1fr_80px_110px_100px_110px_32px] gap-2 items-end">
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
                  <div>
                    {i === 0 && <label className={`${t.textXs} text-xs block mb-1`}>Descuento</label>}
                    <input type="number" step="0.01" value={item.descuento} onChange={e => updateItem(i, 'descuento', e.target.value)} placeholder="0.00" className={`w-full px-3 py-2 border rounded-lg text-sm ${t.input}`} />
                  </div>
                  <div>
                    {i === 0 && <label className={`${t.textXs} text-xs block mb-1`}>Régimen</label>}
                    <select value={item.regimen} onChange={e => updateItem(i, 'regimen', e.target.value)} className={`w-full px-2 py-2 border rounded-lg text-xs ${t.input}`}>
                      {TAX_REGIMES.map(r => (
                        <option key={r.value} value={r.value}>{r.label}</option>
                      ))}
                    </select>
                  </div>
                  <button type="button" onClick={() => removeItem(i)} disabled={items.length <= 1} className={`p-2 ${t.textMuted} hover:text-red-400 cursor-pointer disabled:opacity-30`}>
                    <Trash2 size={16} />
                  </button>
                </div>
              </div>
            ))}
          </div>
          <div className={`flex justify-between mt-3 text-sm ${t.textH}`}>
            {totalDescuentos > 0 && <span className={t.textMuted}>Descuentos: -Q{totalDescuentos.toFixed(2)}</span>}
            <span className="font-semibold ml-auto">Total: Q{subtotal.toFixed(2)}</span>
          </div>
        </div>

        {/* Frase preview */}
        {frases.length > 0 && (
          <div className={`flex items-start gap-2 p-3 rounded-lg border ${t.borderSub} ${t.isDark ? 'bg-slate-800/30' : 'bg-blue-50'}`}>
            <Info size={14} className={`mt-0.5 shrink-0 ${t.textMuted}`} />
            <div>
              <p className={`text-xs font-semibold ${t.textMuted} mb-1`}>Frases que se enviarán a SAT:</p>
              <div className="flex flex-wrap gap-2">
                {frases.map((f, i) => (
                  <span key={i} className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs ${t.badgeBlue}`}>
                    tipo={f.tipo} esc={f.escenario} <span className={t.textXs}>({f.label})</span>
                  </span>
                ))}
              </div>
            </div>
          </div>
        )}

        {error && <p className="text-red-400 text-sm">{error}</p>}

        <button type="submit" disabled={loading} className="flex items-center gap-2 px-6 py-3 bg-accent hover:bg-accent-hover text-white rounded-lg font-medium disabled:opacity-50 cursor-pointer">
          <Send size={16} />
          {loading ? 'Emitiendo...' : 'Emitir factura'}
        </button>
      </form>

      {result && (
        <div className={`mt-6 rounded-xl p-4 sm:p-5 max-w-4xl border ${t.badgeGreen}`}>
          <h3 className="font-semibold mb-3">DTE certificado</h3>
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
