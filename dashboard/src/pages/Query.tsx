import { useEffect, useState } from 'react';
import { api } from '../lib/api';
import { Search, XCircle, FileText, FileCode, Printer, Palette } from 'lucide-react';
import { useTheme } from '../lib/useThemeClasses';

export default function Query() {
  const t = useTheme();
  const [accounts, setAccounts] = useState<any[]>([]);
  const [accountNit, setAccountNit] = useState('');
  const [tab, setTab] = useState<'emitted' | 'received'>('emitted');
  const [items, setItems] = useState<any[]>([]);
  const [filtered, setFiltered] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [annulResult, setAnnulResult] = useState('');
  const [downloading, setDownloading] = useState('');

  const [filterNit, setFilterNit] = useState('');
  const [filterName, setFilterName] = useState('');
  const [filterFrom, setFilterFrom] = useState('');
  const [filterTo, setFilterTo] = useState('');

  useEffect(() => { api.accounts.list().then(setAccounts).catch(() => {}); }, []);

  useEffect(() => {
    let result = items;
    if (filterNit) {
      result = result.filter(i => {
        const nit = i.nitReceptor || i.NITReceptor || i.nitEmisor || i.NITEmisor || '';
        return nit.includes(filterNit);
      });
    }
    if (filterName) {
      const q = filterName.toLowerCase();
      result = result.filter(i => {
        const name = (i.receptor || i.NombreReceptor || i.nombreReceptor || i.emisor || i.NombreEmisor || i.nombreEmisor || '').toLowerCase();
        return name.includes(q);
      });
    }
    if (filterFrom) {
      result = result.filter(i => {
        const d = i.fecha || i.FechaEmision || i.fechaEmision || '';
        return d >= filterFrom;
      });
    }
    if (filterTo) {
      result = result.filter(i => {
        const d = i.fecha || i.FechaEmision || i.fechaEmision || '';
        return d <= filterTo + 'T23:59:59';
      });
    }
    setFiltered(result);
  }, [items, filterNit, filterName, filterFrom, filterTo]);

  async function search() {
    if (!accountNit) return;
    setLoading(true);
    setError('');
    setAnnulResult('');
    try {
      const res = tab === 'emitted'
        ? await api.dte.emitted(accountNit)
        : await api.dte.received(accountNit);
      setItems(res.items || []);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  async function annul(uuid: string, nitReceptor: string = 'CF') {
    if (!confirm(`¿Anular DTE ${uuid}?`)) return;
    try {
      const res = await api.dte.annul({ account_nit: accountNit, uuid, nit_receptor: nitReceptor });
      setAnnulResult(`${uuid}: ${res.estado}`);
      search();
    } catch (err: any) {
      setAnnulResult(`Error: ${err.message}`);
    }
  }

  async function downloadFile(uuid: string, type: 'pdf' | 'xml' | 'custom-pdf' | 'pos', nitReceptor: string = 'CF') {
    setDownloading(`${uuid}-${type}`);
    try {
      if (type === 'pdf') await api.dte.downloadPdf(uuid, accountNit, nitReceptor);
      else if (type === 'xml') await api.dte.downloadXml(uuid, accountNit, nitReceptor);
      else if (type === 'custom-pdf') await api.dte.downloadCustomPdf(uuid, accountNit, nitReceptor);
      else if (type === 'pos') await api.dte.downloadPosReceipt(uuid, accountNit, nitReceptor);
    } catch (err: any) {
      setError(`Error descargando ${type.toUpperCase()}: ${err.message}`);
    } finally {
      setDownloading('');
    }
  }

  function getUuid(item: any) { return item.uuid || item.UUID || item.numeroAutorizacion || ''; }
  function getEstado(item: any) { return item.estado || item.Estado || item.estadoDte || ''; }
  function isAnulado(estado: string) { return estado === 'A' || estado === 'Anulado'; }
  function getNitReceptor(item: any) { return item.nitReceptor || item.NITReceptor || item.nitEmisor || item.NITEmisor || 'CF'; }

  return (
    <div>
      <h2 className={`text-xl sm:text-2xl font-bold ${t.textH} mb-6`}>Consultar DTEs</h2>

      {/* Account + tab selector */}
      <div className="flex flex-col sm:flex-row items-start sm:items-end gap-3 mb-4">
        <div>
          <label className={`${t.textMuted} text-xs block mb-1`}>Cuenta</label>
          <select value={accountNit} onChange={e => setAccountNit(e.target.value)} className={`px-3 py-2 border rounded-lg text-sm ${t.input}`}>
            <option value="">Seleccionar...</option>
            {accounts.filter(a => a.status === 'active').map(a => (
              <option key={a.nit} value={a.nit}>{a.nit}{a.name ? ` — ${a.name}` : ''}</option>
            ))}
          </select>
        </div>
        <div className={`flex rounded-lg overflow-hidden border ${t.border}`}>
          <button onClick={() => setTab('emitted')} className={`px-4 py-2 text-sm cursor-pointer ${tab === 'emitted' ? 'bg-accent text-white' : `${t.text} ${t.isDark ? 'bg-slate-800' : 'bg-slate-50'}`}`}>Emitidos</button>
          <button onClick={() => setTab('received')} className={`px-4 py-2 text-sm cursor-pointer ${tab === 'received' ? 'bg-accent text-white' : `${t.text} ${t.isDark ? 'bg-slate-800' : 'bg-slate-50'}`}`}>Recibidos</button>
        </div>
        <button onClick={search} disabled={loading || !accountNit} className="flex items-center gap-2 px-4 py-2 bg-accent hover:bg-accent-hover text-white rounded-lg text-sm disabled:opacity-50 cursor-pointer">
          <Search size={16} /> {loading ? 'Buscando...' : 'Buscar'}
        </button>
      </div>

      {/* Filters */}
      {items.length > 0 && (
        <div className={`flex flex-wrap gap-3 mb-4 p-3 rounded-xl border ${t.card}`}>
          <div>
            <label className={`${t.textXs} text-xs block mb-1`}>Desde</label>
            <input type="date" value={filterFrom} onChange={e => setFilterFrom(e.target.value)} className={`px-2 py-1.5 border rounded-lg text-xs w-36 ${t.input}`} />
          </div>
          <div>
            <label className={`${t.textXs} text-xs block mb-1`}>Hasta</label>
            <input type="date" value={filterTo} onChange={e => setFilterTo(e.target.value)} className={`px-2 py-1.5 border rounded-lg text-xs w-36 ${t.input}`} />
          </div>
          <div>
            <label className={`${t.textXs} text-xs block mb-1`}>NIT</label>
            <input value={filterNit} onChange={e => setFilterNit(e.target.value)} placeholder="Buscar NIT..." className={`px-2 py-1.5 border rounded-lg text-xs w-32 ${t.input}`} />
          </div>
          <div>
            <label className={`${t.textXs} text-xs block mb-1`}>Nombre</label>
            <input value={filterName} onChange={e => setFilterName(e.target.value)} placeholder="Buscar nombre..." className={`px-2 py-1.5 border rounded-lg text-xs w-40 ${t.input}`} />
          </div>
          {(filterNit || filterName || filterFrom || filterTo) && (
            <div className="flex items-end">
              <button onClick={() => { setFilterNit(''); setFilterName(''); setFilterFrom(''); setFilterTo(''); }} className={`text-xs px-2 py-1.5 rounded-lg cursor-pointer ${t.btnSecondary}`}>
                Limpiar filtros
              </button>
            </div>
          )}
          <div className={`flex items-end ml-auto`}>
            <span className={`text-xs ${t.textMuted}`}>{filtered.length} de {items.length}</span>
          </div>
        </div>
      )}

      {error && <p className="text-red-400 text-sm mb-4">{error}</p>}
      {annulResult && <p className="text-amber-400 text-sm mb-4">{annulResult}</p>}

      {/* Desktop table */}
      <div className={`rounded-xl border overflow-hidden ${t.card} hidden sm:block`}>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className={`border-b ${t.border} ${t.textMuted} text-left`}>
                <th className="px-4 py-3">UUID</th>
                <th className="px-4 py-3">Tipo</th>
                <th className="px-4 py-3">Fecha</th>
                <th className="px-4 py-3">{tab === 'emitted' ? 'Receptor' : 'Emisor'}</th>
                <th className="px-4 py-3">Total</th>
                <th className="px-4 py-3">Estado</th>
                <th className="px-4 py-3">Acciones</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((item: any, i: number) => {
                const uuid = getUuid(item);
                const estado = getEstado(item);
                const anulado = isAnulado(estado);
                const nitR = getNitReceptor(item);
                return (
                  <tr key={i} className={`border-b ${t.borderSub} last:border-0`}>
                    <td className={`px-4 py-3 font-mono text-xs ${t.text}`} title={uuid}>{uuid.slice(0, 8)}...</td>
                    <td className={`px-4 py-3 ${t.textH}`}>{item.tipo || item.Tipo || item.tipoDocumento || '—'}</td>
                    <td className={`px-4 py-3 ${t.textMuted}`}>{item.fecha || item.FechaEmision || item.fechaEmision || '—'}</td>
                    <td className={`px-4 py-3 ${t.text}`}>
                      {tab === 'emitted'
                        ? (item.receptor || item.NombreReceptor || item.nombreReceptor || '—')
                        : (item.emisor || item.NombreEmisor || item.nombreEmisor || '—')}
                    </td>
                    <td className={`px-4 py-3 ${t.textH}`}>Q{item.total || item.MontoTotal || item.montoTotal || '—'}</td>
                    <td className="px-4 py-3">
                      <span className={`px-2 py-0.5 rounded text-xs ${anulado ? t.badgeRed : t.badgeGreen}`}>
                        {anulado ? 'Anulado' : 'Vigente'}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex gap-1">
                        <button onClick={() => downloadFile(uuid, 'pdf', nitR)} disabled={downloading === `${uuid}-pdf`} className={`p-1 rounded ${t.textMuted} hover:text-accent cursor-pointer disabled:opacity-50`} title="PDF SAT">
                          <FileText size={14} />
                        </button>
                        <button onClick={() => downloadFile(uuid, 'custom-pdf', nitR)} disabled={downloading === `${uuid}-custom-pdf`} className={`p-1 rounded ${t.textMuted} hover:text-purple-400 cursor-pointer disabled:opacity-50`} title="PDF Personalizado">
                          <Palette size={14} />
                        </button>
                        <button onClick={() => downloadFile(uuid, 'pos', nitR)} disabled={downloading === `${uuid}-pos`} className={`p-1 rounded ${t.textMuted} hover:text-amber-400 cursor-pointer disabled:opacity-50`} title="Recibo POS">
                          <Printer size={14} />
                        </button>
                        <button onClick={() => downloadFile(uuid, 'xml', nitR)} disabled={downloading === `${uuid}-xml`} className={`p-1 rounded ${t.textMuted} hover:text-accent cursor-pointer disabled:opacity-50`} title="XML">
                          <FileCode size={14} />
                        </button>
                        {!anulado && tab === 'emitted' && (
                          <button onClick={() => annul(uuid, nitR)} className={`p-1 rounded ${t.textMuted} hover:text-red-400 cursor-pointer`} title="Anular">
                            <XCircle size={14} />
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                );
              })}
              {filtered.length === 0 && (
                <tr><td colSpan={7} className={`px-4 py-8 text-center ${t.textXs}`}>{loading ? 'Cargando...' : items.length === 0 ? 'Selecciona una cuenta y busca' : 'Sin resultados con los filtros actuales'}</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Mobile cards */}
      <div className={`sm:hidden rounded-xl border ${t.card} divide-y ${t.borderSub}`}>
        {filtered.map((item: any, i: number) => {
          const uuid = getUuid(item);
          const estado = getEstado(item);
          const anulado = isAnulado(estado);
          const nitR = getNitReceptor(item);
          return (
            <div key={i} className="p-4 space-y-2">
              <div className="flex justify-between items-start">
                <span className={`font-mono text-xs ${t.text}`} title={uuid}>{uuid.slice(0, 12)}...</span>
                <span className={`px-2 py-0.5 rounded text-xs ${anulado ? t.badgeRed : t.badgeGreen}`}>
                  {anulado ? 'Anulado' : 'Vigente'}
                </span>
              </div>
              <div className={`text-sm ${t.textH}`}>{item.tipo || item.Tipo || '—'} · Q{item.total || item.MontoTotal || '—'}</div>
              <div className={`text-xs ${t.textMuted}`}>{item.fecha || item.FechaEmision || '—'}</div>
              <div className="flex gap-3 pt-1 flex-wrap">
                <button onClick={() => downloadFile(uuid, 'pdf', nitR)} className="flex items-center gap-1 text-xs text-accent cursor-pointer"><FileText size={12} /> PDF</button>
                <button onClick={() => downloadFile(uuid, 'custom-pdf', nitR)} className="flex items-center gap-1 text-xs text-purple-400 cursor-pointer"><Palette size={12} /> Custom</button>
                <button onClick={() => downloadFile(uuid, 'pos', nitR)} className="flex items-center gap-1 text-xs text-amber-400 cursor-pointer"><Printer size={12} /> POS</button>
                <button onClick={() => downloadFile(uuid, 'xml', nitR)} className="flex items-center gap-1 text-xs text-accent cursor-pointer"><FileCode size={12} /> XML</button>
                {!anulado && tab === 'emitted' && <button onClick={() => annul(uuid, nitR)} className="text-xs text-red-400 cursor-pointer">Anular</button>}
              </div>
            </div>
          );
        })}
        {filtered.length === 0 && <p className={`p-4 text-center ${t.textXs}`}>{loading ? 'Cargando...' : items.length === 0 ? 'Selecciona una cuenta y busca' : 'Sin resultados'}</p>}
      </div>
    </div>
  );
}
