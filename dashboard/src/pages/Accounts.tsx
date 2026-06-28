import { useEffect, useState } from 'react';
import { api } from '../lib/api';
import { Plus, Trash2, Pencil, X, Search, Loader2, Upload, Palette, Eye } from 'lucide-react';
import { useTheme } from '../lib/useThemeClasses';
import PasswordInput from '../components/PasswordInput';

const API_MODES = [
  { value: 'mixed', label: 'Mixta (fallback inteligente)' },
  { value: 'mobile', label: 'Solo Mobile' },
  { value: 'web', label: 'Solo Web' },
];

export default function Accounts() {
  const t = useTheme();
  const [accounts, setAccounts] = useState<any[]>([]);
  const [showForm, setShowForm] = useState(false);
  const [editNit, setEditNit] = useState<string | null>(null);
  const [form, setForm] = useState({ nit: '', login_password: '', cert_password: '', preferred_api: 'mixed', affiliation: 'GEN', name: '' });
  const [editForm, setEditForm] = useState({ login_password: '', cert_password: '', preferred_api: '', affiliation: '', name: '', branding: { color_primario: '', color_secundario: '', telefono: '', email: '', web: '', logo_b64: '' } });
  const [showBranding, setShowBranding] = useState(false);
  const [error, setError] = useState('');
  const [lookingUp, setLookingUp] = useState(false);
  const [nitHint, setNitHint] = useState('');
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [previewing, setPreviewing] = useState(false);

  const load = () => api.accounts.list().then(setAccounts).catch(() => {});
  useEffect(() => { load(); }, []);

  async function smartLookup() {
    if (!form.nit || form.nit.length < 4) { setNitHint('NIT muy corto'); return; }
    const activeAccount = accounts.find(a => a.status === 'active');
    if (!activeAccount) { setNitHint('Se necesita al menos una cuenta activa para buscar NIT'); return; }
    setLookingUp(true);
    setNitHint('');
    try {
      const res = await api.nit.lookup(activeAccount.nit, form.nit);
      const nombre = res.nombre || '';
      setForm(prev => ({ ...prev, name: nombre }));
      const lower = nombre.toLowerCase();
      if (lower.includes('pequeño contribuyente') || lower.includes('peq')) {
        setForm(prev => ({ ...prev, affiliation: 'PEQ' }));
        setNitHint(`${nombre} (auto-detectado: PEQ)`);
      } else {
        setForm(prev => ({ ...prev, affiliation: 'GEN' }));
        setNitHint(`${nombre} (auto-detectado: GEN)`);
      }
    } catch (err: any) {
      setNitHint(`Error: ${err.message}`);
    } finally {
      setLookingUp(false);
    }
  }

  async function create(e: React.FormEvent) {
    e.preventDefault();
    setError('');
    try {
      await api.accounts.create(form);
      setForm({ nit: '', login_password: '', cert_password: '', preferred_api: 'mixed', affiliation: 'GEN', name: '' });
      setShowForm(false);
      setNitHint('');
      load();
    } catch (err: any) {
      setError(err.message);
    }
  }

  function startEdit(a: any) {
    setEditNit(a.nit);
    const b = a.branding || {};
    setEditForm({
      login_password: '', cert_password: '', preferred_api: a.preferred_api, affiliation: a.affiliation, name: a.name || '',
      branding: { color_primario: b.color_primario || '', color_secundario: b.color_secundario || '', telefono: b.telefono || '', email: b.email || '', web: b.web || '', logo_b64: b.logo_b64 || '' },
    });
    setShowBranding(!!(b.color_primario || b.logo_b64));
  }

  async function saveEdit(e: React.FormEvent) {
    e.preventDefault();
    if (!editNit) return;
    setError('');
    try {
      const data: any = {};
      if (editForm.login_password) data.login_password = editForm.login_password;
      if (editForm.cert_password) data.cert_password = editForm.cert_password;
      data.preferred_api = editForm.preferred_api;
      data.affiliation = editForm.affiliation;
      data.name = editForm.name;
      if (showBranding) {
        data.branding = editForm.branding;
      }
      await api.accounts.update(editNit, data);
      setEditNit(null);
      load();
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function remove(nit: string) {
    if (!confirm(`¿Eliminar cuenta ${nit}? Esto es permanente.`)) return;
    await api.accounts.deactivate(nit);
    load();
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h2 className={`text-xl sm:text-2xl font-bold ${t.textH}`}>Cuentas SAT</h2>
        <button onClick={() => setShowForm(!showForm)} className="flex items-center gap-2 px-3 sm:px-4 py-2 bg-accent hover:bg-accent-hover text-white rounded-lg text-sm cursor-pointer">
          <Plus size={16} /> <span className="hidden sm:inline">Nueva cuenta</span>
        </button>
      </div>

      {showForm && (
        <form onSubmit={create} className={`rounded-xl border p-4 sm:p-5 mb-6 space-y-4 ${t.card}`}>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className={`${t.textXs} text-xs block mb-1`}>NIT</label>
              <div className="flex gap-2">
                <input value={form.nit} onChange={e => setForm({ ...form, nit: e.target.value })} placeholder="120405237" className={`flex-1 px-3 py-2 border rounded-lg text-sm ${t.input}`} required />
                <button type="button" onClick={smartLookup} disabled={lookingUp} className={`px-3 py-2 rounded-lg cursor-pointer ${t.btnSecondary} disabled:opacity-50`} title="Auto-detectar nombre y afiliación">
                  {lookingUp ? <Loader2 size={16} className="animate-spin" /> : <Search size={16} />}
                </button>
              </div>
              {nitHint && <p className={`text-xs mt-1 ${nitHint.startsWith('Error') ? 'text-red-400' : 'text-green-500'}`}>{nitHint}</p>}
            </div>
            <div>
              <label className={`${t.textXs} text-xs block mb-1`}>Nombre (opcional)</label>
              <input value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} placeholder="Se auto-rellena con buscar NIT" className={`w-full px-3 py-2 border rounded-lg text-sm ${t.input}`} />
            </div>
            <select value={form.preferred_api} onChange={e => setForm({ ...form, preferred_api: e.target.value })} className={`px-3 py-2 border rounded-lg text-sm ${t.input}`}>
              {API_MODES.map(m => <option key={m.value} value={m.value}>{m.label}</option>)}
            </select>
            <select value={form.affiliation} onChange={e => setForm({ ...form, affiliation: e.target.value })} className={`px-3 py-2 border rounded-lg text-sm ${t.input}`}>
              <option value="GEN">GEN — General</option>
              <option value="PEQ">PEQ — Pequeño contribuyente</option>
            </select>
            <PasswordInput value={form.login_password} onChange={v => setForm({ ...form, login_password: v })} placeholder="Contraseña login" className={`px-3 py-2 border rounded-lg text-sm ${t.input}`} required />
            <PasswordInput value={form.cert_password} onChange={v => setForm({ ...form, cert_password: v })} placeholder="Contraseña certificación" className={`px-3 py-2 border rounded-lg text-sm ${t.input}`} required />
          </div>
          {error && !editNit && <p className="text-red-400 text-sm">{error}</p>}
          <button type="submit" className="px-4 py-2 bg-accent hover:bg-accent-hover text-white rounded-lg text-sm cursor-pointer">Crear</button>
        </form>
      )}

      {editNit && (
        <form onSubmit={saveEdit} className={`rounded-xl border p-4 sm:p-5 mb-6 space-y-4 ${t.card}`}>
          <div className="flex items-center justify-between mb-2">
            <h3 className={`font-semibold ${t.textH}`}>Editar {editNit}</h3>
            <button type="button" onClick={() => setEditNit(null)} className={`${t.textMuted} cursor-pointer`}><X size={18} /></button>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <input value={editForm.name} onChange={e => setEditForm({ ...editForm, name: e.target.value })} placeholder="Nombre (opcional)" className={`px-3 py-2 border rounded-lg text-sm ${t.input}`} />
            <select value={editForm.preferred_api} onChange={e => setEditForm({ ...editForm, preferred_api: e.target.value })} className={`px-3 py-2 border rounded-lg text-sm ${t.input}`}>
              {API_MODES.map(m => <option key={m.value} value={m.value}>{m.label}</option>)}
            </select>
            <PasswordInput value={editForm.login_password} onChange={v => setEditForm({ ...editForm, login_password: v })} placeholder="Nueva contraseña login (dejar vacío = no cambiar)" className={`px-3 py-2 border rounded-lg text-sm ${t.input}`} />
            <PasswordInput value={editForm.cert_password} onChange={v => setEditForm({ ...editForm, cert_password: v })} placeholder="Nueva contraseña certificación (dejar vacío = no cambiar)" className={`px-3 py-2 border rounded-lg text-sm ${t.input}`} />
            <select value={editForm.affiliation} onChange={e => setEditForm({ ...editForm, affiliation: e.target.value })} className={`px-3 py-2 border rounded-lg text-sm ${t.input}`}>
              <option value="GEN">GEN</option>
              <option value="PEQ">PEQ</option>
            </select>
          </div>
          <div className="pt-2">
            <button type="button" onClick={() => setShowBranding(!showBranding)} className={`flex items-center gap-2 text-xs cursor-pointer ${t.textMuted} hover:text-accent`}>
              <Palette size={14} /> {showBranding ? 'Ocultar branding' : 'Personalizar factura (logo, colores)'}
            </button>
          </div>
          {showBranding && (
            <div className={`rounded-lg border p-4 space-y-3 ${t.isDark ? 'border-slate-600 bg-slate-800/50' : 'border-slate-200 bg-slate-50'}`}>
              <h4 className={`text-sm font-semibold ${t.textH}`}>Branding de Factura</h4>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <label className={`${t.textXs} text-xs block mb-1`}>Color primario</label>
                  <div className="flex gap-2 items-center">
                    <input type="color" value={editForm.branding.color_primario || '#2C3E50'} onChange={e => setEditForm({...editForm, branding: {...editForm.branding, color_primario: e.target.value}})} className="w-8 h-8 rounded cursor-pointer border-0" />
                    <input value={editForm.branding.color_primario} onChange={e => setEditForm({...editForm, branding: {...editForm.branding, color_primario: e.target.value}})} placeholder="#2C3E50" className={`flex-1 px-2 py-1.5 border rounded-lg text-xs font-mono ${t.input}`} />
                  </div>
                </div>
                <div>
                  <label className={`${t.textXs} text-xs block mb-1`}>Color secundario</label>
                  <div className="flex gap-2 items-center">
                    <input type="color" value={editForm.branding.color_secundario || '#34495E'} onChange={e => setEditForm({...editForm, branding: {...editForm.branding, color_secundario: e.target.value}})} className="w-8 h-8 rounded cursor-pointer border-0" />
                    <input value={editForm.branding.color_secundario} onChange={e => setEditForm({...editForm, branding: {...editForm.branding, color_secundario: e.target.value}})} placeholder="#34495E" className={`flex-1 px-2 py-1.5 border rounded-lg text-xs font-mono ${t.input}`} />
                  </div>
                </div>
                <div>
                  <label className={`${t.textXs} text-xs block mb-1`}>Teléfono</label>
                  <input value={editForm.branding.telefono} onChange={e => setEditForm({...editForm, branding: {...editForm.branding, telefono: e.target.value}})} placeholder="+502 3014 9000" className={`w-full px-2 py-1.5 border rounded-lg text-xs ${t.input}`} />
                </div>
                <div>
                  <label className={`${t.textXs} text-xs block mb-1`}>Email</label>
                  <input value={editForm.branding.email} onChange={e => setEditForm({...editForm, branding: {...editForm.branding, email: e.target.value}})} placeholder="contacto@empresa.com" className={`w-full px-2 py-1.5 border rounded-lg text-xs ${t.input}`} />
                </div>
                <div>
                  <label className={`${t.textXs} text-xs block mb-1`}>Sitio web</label>
                  <input value={editForm.branding.web} onChange={e => setEditForm({...editForm, branding: {...editForm.branding, web: e.target.value}})} placeholder="empresa.com" className={`w-full px-2 py-1.5 border rounded-lg text-xs ${t.input}`} />
                </div>
                <div>
                  <label className={`${t.textXs} text-xs block mb-1`}>Logo (PNG/JPG)</label>
                  <label className={`flex items-center gap-2 px-3 py-1.5 rounded-lg cursor-pointer text-xs ${t.btnSecondary}`}>
                    <Upload size={12} /> {editForm.branding.logo_b64 ? 'Logo cargado' : 'Subir logo'}
                    <input type="file" accept="image/png,image/jpeg" className="hidden" onChange={e => {
                      const file = e.target.files?.[0];
                      if (!file) return;
                      const reader = new FileReader();
                      reader.onload = () => {
                        const b64 = (reader.result as string).split(',')[1];
                        setEditForm(prev => ({...prev, branding: {...prev.branding, logo_b64: b64}}));
                      };
                      reader.readAsDataURL(file);
                    }} />
                  </label>
                </div>
              </div>
              {editForm.branding.logo_b64 && (
                <div className="flex items-center gap-3">
                  <img src={`data:image/png;base64,${editForm.branding.logo_b64}`} className="h-10 rounded" alt="Logo preview" />
                  <button type="button" onClick={() => setEditForm({...editForm, branding: {...editForm.branding, logo_b64: ''}})} className="text-xs text-red-400 cursor-pointer">Quitar logo</button>
                </div>
              )}
              <button type="button" disabled={previewing} onClick={async () => {
                if (!editNit) return;
                setPreviewing(true);
                try {
                  const url = await api.accounts.previewPdf(editNit, editForm.branding);
                  setPreviewUrl(url);
                } catch (err: any) {
                  setError(`Preview: ${err.message}`);
                } finally {
                  setPreviewing(false);
                }
              }} className={`flex items-center gap-2 px-3 py-1.5 rounded-lg cursor-pointer text-xs ${t.btnSecondary} disabled:opacity-50`}>
                {previewing ? <Loader2 size={12} className="animate-spin" /> : <Eye size={12} />}
                Vista previa de factura
              </button>
            </div>
          )}
          {error && editNit && <p className="text-red-400 text-sm">{error}</p>}
          <button type="submit" className="px-4 py-2 bg-accent hover:bg-accent-hover text-white rounded-lg text-sm cursor-pointer">Guardar</button>
        </form>
      )}

      <div className={`rounded-xl border overflow-hidden ${t.card}`}>
        <div className="hidden sm:block overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className={`border-b ${t.border} ${t.textMuted} text-left`}>
                <th className="px-4 py-3">NIT</th>
                <th className="px-4 py-3">Nombre</th>
                <th className="px-4 py-3">Afiliación</th>
                <th className="px-4 py-3">API</th>
                <th className="px-4 py-3">Estado</th>
                <th className="px-4 py-3"></th>
              </tr>
            </thead>
            <tbody>
              {accounts.map(a => (
                <tr key={a.nit} className={`border-b ${t.borderSub} last:border-0`}>
                  <td className={`px-4 py-3 ${t.textH} font-mono`}>{a.nit}</td>
                  <td className={`px-4 py-3 ${t.text}`}>{a.name || '—'}</td>
                  <td className="px-4 py-3"><span className={`px-2 py-0.5 rounded text-xs ${a.affiliation === 'PEQ' ? t.badgeAmber : t.badge}`}>{a.affiliation}</span></td>
                  <td className={`px-4 py-3 ${t.textMuted}`}>{a.preferred_api}</td>
                  <td className="px-4 py-3">
                    <span className={`px-2 py-0.5 rounded text-xs ${a.status === 'active' ? t.badgeGreen : t.badgeRed}`}>
                      {a.status}
                    </span>
                  </td>
                  <td className="px-4 py-3 flex gap-2">
                    <button onClick={() => startEdit(a)} className={`${t.textMuted} hover:text-accent cursor-pointer`}><Pencil size={16} /></button>
                    <button onClick={() => remove(a.nit)} className={`${t.textMuted} hover:text-red-400 cursor-pointer`}><Trash2 size={16} /></button>
                  </td>
                </tr>
              ))}
              {accounts.length === 0 && (
                <tr><td colSpan={6} className={`px-4 py-8 text-center ${t.textXs}`}>Sin cuentas registradas</td></tr>
              )}
            </tbody>
          </table>
        </div>
        <div className="sm:hidden divide-y divide-slate-700/50">
          {accounts.map(a => (
            <div key={a.nit} className="p-4 space-y-2">
              <div className="flex items-center justify-between">
                <span className={`${t.textH} font-mono font-bold`}>{a.nit}</span>
                <span className={`px-2 py-0.5 rounded text-xs ${a.status === 'active' ? t.badgeGreen : t.badgeRed}`}>{a.status}</span>
              </div>
              <div className={`text-sm ${t.text}`}>{a.name || '—'} · {a.affiliation} · {a.preferred_api}</div>
              <div className="flex gap-2">
                <button onClick={() => startEdit(a)} className="text-xs text-accent cursor-pointer">Editar</button>
                <button onClick={() => remove(a.nit)} className="text-xs text-red-400 cursor-pointer">Eliminar</button>
              </div>
            </div>
          ))}
          {accounts.length === 0 && <p className={`p-4 text-center ${t.textXs}`}>Sin cuentas registradas</p>}
        </div>
      </div>

      {previewUrl && (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 p-4" onClick={() => { URL.revokeObjectURL(previewUrl); setPreviewUrl(null); }}>
          <div className={`relative w-full max-w-3xl h-[85vh] rounded-xl overflow-hidden ${t.card}`} onClick={e => e.stopPropagation()}>
            <div className={`flex items-center justify-between px-4 py-2 border-b ${t.border}`}>
              <span className={`text-sm font-semibold ${t.textH}`}>Vista previa de factura</span>
              <button onClick={() => { URL.revokeObjectURL(previewUrl); setPreviewUrl(null); }} className={`${t.textMuted} hover:text-red-400 cursor-pointer`}><X size={18} /></button>
            </div>
            <iframe src={previewUrl} className="w-full h-full" title="Preview PDF" />
          </div>
        </div>
      )}
    </div>
  );
}
