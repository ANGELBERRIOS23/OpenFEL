import { useState } from 'react';
import { Play, Copy, Check, ChevronDown, Trash2 } from 'lucide-react';
import { useTheme } from '../lib/useThemeClasses';

const PRESETS = [
  { name: 'Health check', method: 'GET', path: '/api/health', body: '' },
  { name: 'Listar cuentas', method: 'GET', path: '/api/accounts', body: '' },
  { name: 'Listar keys', method: 'GET', path: '/api/keys', body: '' },
  { name: 'Listar emitidos', method: 'GET', path: '/api/dte/emitted?account_nit=', body: '' },
  { name: 'Listar recibidos', method: 'GET', path: '/api/dte/received?account_nit=', body: '' },
  { name: 'Buscar NIT', method: 'POST', path: '/api/nit/lookup', body: JSON.stringify({ account_nit: '', nit: 'CF' }, null, 2) },
  { name: 'Emitir FACT', method: 'POST', path: '/api/dte/emit', body: JSON.stringify({
    account_nit: '', tipo: 'FACT', receptor_nit: 'CF', receptor_nombre: 'Consumidor Final',
    items: [{ descripcion: 'Servicio', cantidad: 1, precio_unitario: 100.00, descuento: 0, regimen: 'GENERAL' }],
  }, null, 2) },
  { name: 'Emitir FPEQ', method: 'POST', path: '/api/dte/emit', body: JSON.stringify({
    account_nit: '', tipo: 'FPEQ', receptor_nit: 'CF', receptor_nombre: 'Consumidor Final',
    items: [{ descripcion: 'Servicio', cantidad: 1, precio_unitario: 100.00, descuento: 0 }],
  }, null, 2) },
  { name: 'Anular DTE', method: 'POST', path: '/api/dte/annul', body: JSON.stringify({
    account_nit: '', uuid: '', motivo: 'Anulación de prueba',
  }, null, 2) },
  { name: 'Crear cuenta', method: 'POST', path: '/api/accounts', body: JSON.stringify({
    nit: '', login_password: '', cert_password: '', preferred_api: 'mixed', affiliation: 'GEN', name: '',
  }, null, 2) },
  { name: 'Crear API key', method: 'POST', path: '/api/keys', body: JSON.stringify({
    name: 'Test key', role: 'VIEWER', allowed_accounts: [],
  }, null, 2) },
  { name: 'Audit log', method: 'GET', path: '/api/logs?limit=10', body: '' },
  { name: 'Descargar PDF', method: 'GET', path: '/api/dte/{uuid}/pdf?account_nit=&nit_receptor=CF', body: '' },
  { name: 'PDF Personalizado', method: 'GET', path: '/api/dte/{uuid}/custom-pdf?account_nit=&nit_receptor=CF', body: '' },
  { name: 'Recibo POS', method: 'GET', path: '/api/dte/{uuid}/pos-receipt?account_nit=&nit_receptor=CF&width=80', body: '' },
  { name: 'Descargar XML', method: 'GET', path: '/api/dte/{uuid}/xml?account_nit=&nit_receptor=CF', body: '' },
];

interface HistoryEntry {
  method: string;
  path: string;
  status: number;
  time: number;
  timestamp: string;
}

export default function Playground() {
  const t = useTheme();
  const [method, setMethod] = useState('GET');
  const [path, setPath] = useState('/api/health');
  const [body, setBody] = useState('');
  const [response, setResponse] = useState<string | null>(null);
  const [status, setStatus] = useState(0);
  const [responseTime, setResponseTime] = useState(0);
  const [responseHeaders, setResponseHeaders] = useState('');
  const [loading, setLoading] = useState(false);
  const [copied, setCopied] = useState(false);
  const [showPresets, setShowPresets] = useState(false);
  const [history, setHistory] = useState<HistoryEntry[]>([]);
  const [activeTab, setActiveTab] = useState<'body' | 'headers'>('body');
  const [responseTab, setResponseTab] = useState<'body' | 'headers'>('body');

  const apiKey = sessionStorage.getItem('openfel_key') || '';

  async function send() {
    setLoading(true);
    setResponse(null);
    setStatus(0);
    setResponseHeaders('');
    const t0 = performance.now();
    try {
      const opts: RequestInit = {
        method,
        headers: {
          'X-API-Key': apiKey,
          ...(body ? { 'Content-Type': 'application/json' } : {}),
        },
      };
      if (body && method !== 'GET') opts.body = body;
      const res = await fetch(path, opts);
      const elapsed = Math.round(performance.now() - t0);
      setStatus(res.status);
      setResponseTime(elapsed);

      const hdrs = Array.from(res.headers.entries())
        .map(([k, v]) => `${k}: ${v}`).join('\n');
      setResponseHeaders(hdrs);

      const ct = res.headers.get('content-type') || '';
      if (ct.includes('json')) {
        const data = await res.json();
        setResponse(JSON.stringify(data, null, 2));
      } else if (ct.includes('pdf') || ct.includes('octet')) {
        const blob = await res.blob();
        setResponse(`[Binary: ${blob.size} bytes, type: ${ct}]`);
        if (blob.size > 0) {
          const url = URL.createObjectURL(blob);
          const a = document.createElement('a');
          a.href = url;
          a.download = path.includes('pdf') ? 'download.pdf' : path.includes('xml') ? 'download.xml' : 'download.bin';
          a.click();
          URL.revokeObjectURL(url);
        }
      } else {
        const text = await res.text();
        setResponse(text || '[Empty response]');
      }

      setHistory(prev => [{
        method, path, status: res.status, time: elapsed,
        timestamp: new Date().toLocaleTimeString(),
      }, ...prev].slice(0, 20));
    } catch (err: any) {
      setStatus(0);
      setResponseTime(Math.round(performance.now() - t0));
      setResponse(`Network error: ${err.message}`);
    } finally {
      setLoading(false);
    }
  }

  function loadPreset(p: typeof PRESETS[0]) {
    setMethod(p.method);
    setPath(p.path);
    setBody(p.body);
    setShowPresets(false);
    setResponse(null);
  }

  function copyResponse() {
    if (response) {
      navigator.clipboard.writeText(response);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  }

  function curlCommand() {
    let cmd = `curl -X ${method}`;
    cmd += ` -H "X-API-Key: \${API_KEY}"`;
    if (body && method !== 'GET') {
      cmd += ` -H "Content-Type: application/json"`;
      cmd += ` -d '${body.replace(/\n/g, '')}'`;
    }
    cmd += ` http://localhost:8000${path}`;
    return cmd;
  }

  const statusColor = status >= 200 && status < 300 ? t.badgeGreen :
    status >= 400 ? t.badgeRed : status >= 300 ? t.badgeAmber : t.badge;

  return (
    <div>
      <h2 className={`text-xl sm:text-2xl font-bold ${t.textH} mb-6`}>API Playground</h2>

      {/* URL bar */}
      <div className={`rounded-xl border p-4 mb-4 ${t.card}`}>
        <div className="flex flex-col sm:flex-row gap-2 mb-3">
          <select value={method} onChange={e => setMethod(e.target.value)}
            className={`px-3 py-2 border rounded-lg text-sm font-mono font-bold w-full sm:w-28 ${t.input} ${
              method === 'GET' ? 'text-green-500' : method === 'POST' ? 'text-blue-500' :
              method === 'PATCH' ? 'text-amber-500' : method === 'DELETE' ? 'text-red-500' : ''
            }`}>
            <option>GET</option>
            <option>POST</option>
            <option>PATCH</option>
            <option>DELETE</option>
          </select>
          <input value={path} onChange={e => setPath(e.target.value)}
            placeholder="/api/..."
            className={`flex-1 px-3 py-2 border rounded-lg text-sm font-mono ${t.input}`}
            onKeyDown={e => e.key === 'Enter' && send()} />
          <button onClick={send} disabled={loading}
            className="flex items-center gap-2 px-5 py-2 bg-accent hover:bg-accent-hover text-white rounded-lg text-sm font-semibold disabled:opacity-50 cursor-pointer">
            <Play size={14} /> {loading ? 'Enviando...' : 'Enviar'}
          </button>
          <div className="relative">
            <button onClick={() => setShowPresets(!showPresets)}
              className={`flex items-center gap-1 px-3 py-2 rounded-lg text-sm cursor-pointer ${t.btnSecondary}`}>
              Presets <ChevronDown size={14} />
            </button>
            {showPresets && (
              <div className={`absolute right-0 top-full mt-1 w-56 rounded-lg border shadow-lg z-50 ${t.card} max-h-80 overflow-y-auto`}>
                {PRESETS.map((p, i) => (
                  <button key={i} onClick={() => loadPreset(p)}
                    className={`w-full text-left px-3 py-2 text-sm cursor-pointer hover:bg-accent/10 flex items-center gap-2 ${t.text}`}>
                    <span className={`font-mono text-xs w-12 ${
                      p.method === 'GET' ? 'text-green-500' : p.method === 'POST' ? 'text-blue-500' :
                      p.method === 'DELETE' ? 'text-red-500' : 'text-amber-500'
                    }`}>{p.method}</span>
                    {p.name}
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Request tabs */}
        <div className={`flex gap-1 mb-2 border-b ${t.borderSub}`}>
          <button onClick={() => setActiveTab('body')}
            className={`px-3 py-1.5 text-xs cursor-pointer ${activeTab === 'body' ? `${t.textH} border-b-2 border-accent` : t.textMuted}`}>
            Body
          </button>
          <button onClick={() => setActiveTab('headers')}
            className={`px-3 py-1.5 text-xs cursor-pointer ${activeTab === 'headers' ? `${t.textH} border-b-2 border-accent` : t.textMuted}`}>
            Headers
          </button>
        </div>

        {activeTab === 'body' && method !== 'GET' && (
          <textarea value={body} onChange={e => setBody(e.target.value)}
            rows={Math.min(Math.max(body.split('\n').length, 3), 15)}
            placeholder='{"key": "value"}'
            className={`w-full px-3 py-2 border rounded-lg text-xs font-mono ${t.input}`} />
        )}
        {activeTab === 'body' && method === 'GET' && (
          <p className={`text-xs ${t.textMuted} py-2`}>GET requests don't have a body. Use query params in the URL.</p>
        )}
        {activeTab === 'headers' && (
          <div className={`text-xs font-mono ${t.textMuted} py-2 space-y-1`}>
            <div>X-API-Key: {apiKey ? `${apiKey.slice(0, 20)}...` : '(not set — login first)'}</div>
            {body && method !== 'GET' && <div>Content-Type: application/json</div>}
          </div>
        )}
      </div>

      {/* Response panel */}
      {(response !== null || loading) && (
        <div className={`rounded-xl border p-4 mb-4 ${t.card}`}>
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-3">
              <h3 className={`font-semibold text-sm ${t.textH}`}>Respuesta</h3>
              {status > 0 && (
                <>
                  <span className={`px-2 py-0.5 rounded text-xs font-mono font-bold ${statusColor}`}>{status}</span>
                  <span className={`text-xs ${t.textMuted}`}>{responseTime}ms</span>
                </>
              )}
            </div>
            <div className="flex gap-2">
              <button onClick={copyResponse} className={`flex items-center gap-1 text-xs cursor-pointer ${t.textMuted} hover:text-accent`}>
                {copied ? <Check size={12} /> : <Copy size={12} />} {copied ? 'Copiado' : 'Copiar'}
              </button>
            </div>
          </div>

          <div className={`flex gap-1 mb-2 border-b ${t.borderSub}`}>
            <button onClick={() => setResponseTab('body')}
              className={`px-3 py-1.5 text-xs cursor-pointer ${responseTab === 'body' ? `${t.textH} border-b-2 border-accent` : t.textMuted}`}>
              Body
            </button>
            <button onClick={() => setResponseTab('headers')}
              className={`px-3 py-1.5 text-xs cursor-pointer ${responseTab === 'headers' ? `${t.textH} border-b-2 border-accent` : t.textMuted}`}>
              Headers
            </button>
            <button onClick={() => { navigator.clipboard.writeText(curlCommand()); }}
              className={`px-3 py-1.5 text-xs cursor-pointer ${t.textMuted} hover:text-accent ml-auto`}>
              Copiar curl
            </button>
          </div>

          {responseTab === 'body' && (
            <pre className={`text-xs p-3 rounded-lg overflow-x-auto max-h-96 overflow-y-auto ${t.codeBg}`}>
              {loading ? 'Loading...' : response}
            </pre>
          )}
          {responseTab === 'headers' && (
            <pre className={`text-xs p-3 rounded-lg overflow-x-auto ${t.codeBg}`}>
              {responseHeaders || 'No headers'}
            </pre>
          )}
        </div>
      )}

      {/* History */}
      {history.length > 0 && (
        <div className={`rounded-xl border p-4 ${t.card}`}>
          <div className="flex items-center justify-between mb-3">
            <h3 className={`font-semibold text-sm ${t.textH}`}>Historial</h3>
            <button onClick={() => setHistory([])} className={`text-xs cursor-pointer ${t.textMuted} hover:text-red-400`}>
              <Trash2 size={12} />
            </button>
          </div>
          <div className="space-y-1">
            {history.map((h, i) => (
              <button key={i} onClick={() => { setMethod(h.method); setPath(h.path); }}
                className={`w-full flex items-center gap-2 px-2 py-1.5 rounded text-xs cursor-pointer hover:bg-accent/10 ${t.text}`}>
                <span className={`font-mono w-12 text-left font-bold ${
                  h.method === 'GET' ? 'text-green-500' : h.method === 'POST' ? 'text-blue-500' :
                  h.method === 'DELETE' ? 'text-red-500' : 'text-amber-500'
                }`}>{h.method}</span>
                <span className="font-mono flex-1 text-left truncate">{h.path}</span>
                <span className={`px-1.5 py-0.5 rounded font-mono ${
                  h.status < 300 ? t.badgeGreen : h.status >= 400 ? t.badgeRed : t.badgeAmber
                }`}>{h.status}</span>
                <span className={t.textXs}>{h.time}ms</span>
                <span className={t.textXs}>{h.timestamp}</span>
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
