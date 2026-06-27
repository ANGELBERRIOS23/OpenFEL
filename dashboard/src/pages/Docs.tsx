import { useState } from 'react';
import { api } from '../lib/api';
import { Play, ChevronDown, ChevronRight, Copy, Check } from 'lucide-react';
import { useTheme } from '../lib/useThemeClasses';

const endpoints = [
  {
    section: 'Health',
    items: [
      { method: 'GET', path: '/api/health', role: 'público', desc: 'Estado de los 4 servidores SAT (DNS, TLS, HTTP, latencia). No requiere API key.',
        tryable: true, tryFn: () => api.health() },
    ],
  },
  {
    section: 'NIT',
    items: [
      { method: 'POST', path: '/api/nit/lookup', role: 'VIEWER', desc: 'Consultar nombre de un NIT en el RTU.',
        body: '{ "account_nit": "120405237", "nit": "CF" }',
        tryable: true, tryFn: (body: any) => api.nit.lookup(body.account_nit, body.nit) },
    ],
  },
  {
    section: 'DTE (Documentos Tributarios)',
    items: [
      { method: 'POST', path: '/api/dte/emit', role: 'OPERATOR',
        desc: 'Emitir un DTE. Soporta descuento y régimen por ítem (GENERAL, EXENTO, EXPORT, PEQ, NO_AFECTO, TURISMO_HOSPEDAJE).',
        body: `{
  "account_nit": "120405237",
  "tipo": "FACT",
  "receptor_nit": "CF",
  "receptor_nombre": "Consumidor Final",
  "items": [
    {
      "descripcion": "Servicio profesional",
      "cantidad": 1,
      "precio_unitario": 500.00,
      "descuento": 0,
      "regimen": "GENERAL"
    }
  ]
}` },
      { method: 'POST', path: '/api/dte/annul', role: 'OPERATOR', desc: 'Anular un DTE por UUID.',
        body: '{ "account_nit": "120405237", "uuid": "UUID-AQUI", "motivo": "Error en datos" }' },
      { method: 'GET', path: '/api/dte/emitted?account_nit=X', role: 'VIEWER', desc: 'Listar últimos DTEs emitidos (hasta 100).',
        tryable: true, tryParam: 'account_nit',
        tryFn: (p: any) => api.dte.emitted(p.account_nit) },
      { method: 'GET', path: '/api/dte/received?account_nit=X', role: 'VIEWER', desc: 'Listar últimos DTEs recibidos (hasta 100).',
        tryable: true, tryParam: 'account_nit',
        tryFn: (p: any) => api.dte.received(p.account_nit) },
      { method: 'GET', path: '/api/dte/{uuid}/detail?account_nit=X', role: 'VIEWER', desc: 'Detalle completo de un DTE por UUID.' },
      { method: 'GET', path: '/api/dte/{uuid}/pdf?account_nit=X', role: 'VIEWER', desc: 'Descargar PDF de un DTE.' },
      { method: 'GET', path: '/api/dte/{uuid}/xml?account_nit=X', role: 'VIEWER', desc: 'Descargar XML de un DTE (requiere API web o mixta).' },
    ],
  },
  {
    section: 'Cuentas SAT',
    items: [
      { method: 'GET', path: '/api/accounts', role: 'ADMIN', desc: 'Listar todas las cuentas SAT registradas.',
        tryable: true, tryFn: () => api.accounts.list() },
      { method: 'POST', path: '/api/accounts', role: 'ADMIN', desc: 'Crear cuenta. Soporta auto-detección de nombre y afiliación vía NIT lookup.',
        body: '{ "nit": "120405237", "login_password": "...", "cert_password": "...", "preferred_api": "mixed", "affiliation": "GEN", "name": "" }' },
      { method: 'GET', path: '/api/accounts/{nit}', role: 'ADMIN', desc: 'Obtener detalle de una cuenta.' },
      { method: 'PATCH', path: '/api/accounts/{nit}', role: 'ADMIN', desc: 'Editar cuenta (contraseñas, modo API, afiliación, nombre, estado).' },
      { method: 'DELETE', path: '/api/accounts/{nit}', role: 'ADMIN', desc: 'Eliminar cuenta permanentemente.' },
    ],
  },
  {
    section: 'API Keys',
    items: [
      { method: 'GET', path: '/api/keys', role: 'ADMIN', desc: 'Listar todas las API keys.',
        tryable: true, tryFn: () => api.keys.list() },
      { method: 'POST', path: '/api/keys', role: 'ADMIN', desc: 'Crear key. La key completa se muestra solo una vez.',
        body: '{ "name": "Mi Key", "role": "VIEWER", "allowed_accounts": [] }' },
      { method: 'PATCH', path: '/api/keys/{id}', role: 'ADMIN', desc: 'Actualizar key (nombre, rol, estado, cuentas permitidas).' },
      { method: 'DELETE', path: '/api/keys/{id}', role: 'ADMIN', desc: 'Revocar key (soft delete).' },
    ],
  },
  {
    section: 'Audit Log',
    items: [
      { method: 'GET', path: '/api/logs', role: 'ADMIN', desc: 'Consultar log de auditoría. Query params: action, account_nit, limit, offset.',
        tryable: true, tryFn: () => api.logs.list({ limit: '5' }) },
    ],
  },
];

function TryPanel({ ep, t }: { ep: any; t: ReturnType<typeof useTheme> }) {
  const [input, setInput] = useState(ep.body || (ep.tryParam ? `{ "${ep.tryParam}": "" }` : ''));
  const [result, setResult] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  async function run() {
    setLoading(true);
    setError('');
    setResult(null);
    try {
      const parsed = input.trim() ? JSON.parse(input) : undefined;
      const res = await ep.tryFn(parsed);
      setResult(JSON.stringify(res, null, 2));
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className={`mt-3 p-3 rounded-lg border ${t.borderSub} ${t.isDark ? 'bg-slate-800/50' : 'bg-slate-50'}`}>
      {(ep.body || ep.tryParam) && (
        <textarea
          value={input}
          onChange={e => setInput(e.target.value)}
          rows={Math.min(input.split('\n').length + 1, 10)}
          className={`w-full px-3 py-2 border rounded-lg text-xs font-mono mb-2 ${t.input}`}
        />
      )}
      <button onClick={run} disabled={loading} className="flex items-center gap-1 px-3 py-1.5 bg-accent hover:bg-accent-hover text-white rounded-lg text-xs disabled:opacity-50 cursor-pointer">
        <Play size={12} /> {loading ? 'Ejecutando...' : 'Probar'}
      </button>
      {error && <p className="text-red-400 text-xs mt-2">{error}</p>}
      {result && (
        <pre className={`mt-2 p-2 rounded-lg text-xs overflow-x-auto max-h-64 overflow-y-auto ${t.codeBg}`}>{result}</pre>
      )}
    </div>
  );
}

export default function Docs() {
  const t = useTheme();
  const [open, setOpen] = useState<Record<string, boolean>>({});
  const [copied, setCopied] = useState(false);

  function toggle(key: string) {
    setOpen(prev => ({ ...prev, [key]: !prev[key] }));
  }

  function copyExample() {
    navigator.clipboard.writeText(`curl -X POST http://localhost:8000/api/dte/emit \\
  -H "Content-Type: application/json" \\
  -H "X-API-Key: ofel_k1_..." \\
  -d '{
    "account_nit": "120405237",
    "tipo": "FACT",
    "receptor_nit": "CF",
    "receptor_nombre": "Consumidor Final",
    "items": [
      {"descripcion": "Servicio profesional", "cantidad": 1, "precio_unitario": 500.00, "descuento": 0, "regimen": "GENERAL"}
    ]
  }'`);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  return (
    <div className="max-w-4xl">
      <h2 className={`text-xl sm:text-2xl font-bold ${t.textH} mb-2`}>Documentación API</h2>
      <p className={`${t.textMuted} text-sm mb-6`}>
        Todos los endpoints (excepto /api/health) requieren el header <code className={`px-1 rounded ${t.badge} text-xs`}>X-API-Key</code>. Los endpoints marcados con <Play size={10} className="inline text-accent" /> se pueden probar en vivo.
      </p>

      {/* Roles */}
      <div className={`rounded-xl border p-4 sm:p-5 mb-6 ${t.card}`}>
        <h3 className={`font-semibold ${t.textH} mb-3`}>Roles</h3>
        <div className="space-y-2 text-sm">
          <div><span className={`inline-block w-24 px-2 py-0.5 rounded text-xs ${t.badge}`}>VIEWER</span> <span className={t.text}>Solo lectura: consultar NIT, listar DTEs, descargar PDF/XML, ver health</span></div>
          <div><span className={`inline-block w-24 px-2 py-0.5 rounded text-xs ${t.badgeBlue}`}>OPERATOR</span> <span className={t.text}>+ Emitir y anular DTEs</span></div>
          <div><span className={`inline-block w-24 px-2 py-0.5 rounded text-xs ${t.badgePurple}`}>ADMIN</span> <span className={t.text}>+ Gestionar cuentas, API keys, ver logs</span></div>
        </div>
      </div>

      {/* API modes */}
      <div className={`rounded-xl border p-4 sm:p-5 mb-6 ${t.card}`}>
        <h3 className={`font-semibold ${t.textH} mb-3`}>Modos de API por cuenta</h3>
        <div className="space-y-2 text-sm">
          <div><span className={`inline-block w-20 font-mono text-xs ${t.textH}`}>mixed</span> <span className={t.text}>Inteligente: usa mobile (rápida, 12h token) y cae a web automáticamente. Para consultas con fecha o XML usa web.</span></div>
          <div><span className={`inline-block w-20 font-mono text-xs ${t.textH}`}>mobile</span> <span className={t.text}>Solo API móvil. Más rápida (~5s), token 12h, sin descarga XML ni filtro por fechas.</span></div>
          <div><span className={`inline-block w-20 font-mono text-xs ${t.textH}`}>web</span> <span className={t.text}>Solo API web. Sesión 25min, soporta XML, XLS, filtro por fechas, pero más lenta (~10s).</span></div>
        </div>
      </div>

      {/* Tax regimes */}
      <div className={`rounded-xl border p-4 sm:p-5 mb-6 ${t.card}`}>
        <h3 className={`font-semibold ${t.textH} mb-3`}>Regímenes fiscales por ítem</h3>
        <p className={`${t.textMuted} text-sm mb-3`}>Cada ítem puede tener su propio régimen fiscal. OpenFEL genera automáticamente las frases y complementos correspondientes.</p>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-sm">
          <div><span className={`inline-block w-40 px-2 py-0.5 rounded text-xs ${t.badgeGreen}`}>GENERAL</span> <span className={t.text}>IVA 12%</span></div>
          <div><span className={`inline-block w-40 px-2 py-0.5 rounded text-xs ${t.badgeBlue}`}>EXENTO</span> <span className={t.text}>Exento de IVA</span></div>
          <div><span className={`inline-block w-40 px-2 py-0.5 rounded text-xs ${t.badgePurple}`}>EXPORT</span> <span className={t.text}>Exportación (con complemento)</span></div>
          <div><span className={`inline-block w-40 px-2 py-0.5 rounded text-xs ${t.badgeAmber}`}>PEQ</span> <span className={t.text}>Pequeño contribuyente</span></div>
          <div><span className={`inline-block w-40 px-2 py-0.5 rounded text-xs ${t.badge}`}>NO_AFECTO</span> <span className={t.text}>No afecto a impuesto</span></div>
          <div><span className={`inline-block w-40 px-2 py-0.5 rounded text-xs ${t.badgeRed}`}>TURISMO_HOSPEDAJE</span> <span className={t.text}>Turismo 10%</span></div>
        </div>
      </div>

      {/* Endpoints */}
      {endpoints.map(section => (
        <div key={section.section} className="mb-6">
          <h3 className={`font-semibold ${t.textH} mb-3`}>{section.section}</h3>
          <div className={`rounded-xl border overflow-hidden ${t.card}`}>
            {section.items.map((ep, i) => {
              const key = `${section.section}-${i}`;
              const isOpen = open[key];
              return (
                <div key={i} className={`${i > 0 ? `border-t ${t.borderSub}` : ''}`}>
                  <div className="p-3 sm:p-4">
                    <div className="flex flex-wrap items-center gap-2 mb-1">
                      <span className={`px-2 py-0.5 rounded text-xs font-mono font-bold ${
                        ep.method === 'GET' ? t.badgeGreen :
                        ep.method === 'POST' ? t.badgeBlue :
                        ep.method === 'PATCH' ? t.badgeAmber :
                        ep.method === 'DELETE' ? t.badgeRed : t.badge
                      }`}>{ep.method}</span>
                      <code className={`text-xs sm:text-sm font-mono ${t.textH} break-all`}>{ep.path}</code>
                      <span className={`px-2 py-0.5 rounded text-xs ${t.badge}`}>{ep.role}</span>
                      {ep.tryable && (
                        <button onClick={() => toggle(key)} className="flex items-center gap-1 px-2 py-0.5 rounded text-xs text-accent cursor-pointer hover:underline">
                          {isOpen ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
                          Probar
                        </button>
                      )}
                    </div>
                    <p className={`${t.textMuted} text-xs sm:text-sm`}>{ep.desc}</p>
                    {isOpen && ep.tryable && <TryPanel ep={ep} t={t} />}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      ))}

      {/* curl example */}
      <div className={`rounded-xl border p-4 sm:p-5 mb-6 ${t.card}`}>
        <div className="flex items-center justify-between mb-3">
          <h3 className={`font-semibold ${t.textH}`}>Ejemplo: emitir factura con curl</h3>
          <button onClick={copyExample} className={`flex items-center gap-1 text-xs cursor-pointer ${t.textMuted} hover:text-accent`}>
            {copied ? <Check size={14} /> : <Copy size={14} />} {copied ? 'Copiado' : 'Copiar'}
          </button>
        </div>
        <pre className={`text-xs p-3 rounded-lg overflow-x-auto ${t.codeBg}`}>{`curl -X POST http://localhost:8000/api/dte/emit \\
  -H "Content-Type: application/json" \\
  -H "X-API-Key: ofel_k1_..." \\
  -d '{
    "account_nit": "120405237",
    "tipo": "FACT",
    "receptor_nit": "CF",
    "receptor_nombre": "Consumidor Final",
    "items": [
      {
        "descripcion": "Servicio profesional",
        "cantidad": 1,
        "precio_unitario": 500.00,
        "descuento": 0,
        "regimen": "GENERAL"
      }
    ]
  }'`}</pre>
      </div>

      {/* Sandbox info */}
      <div className={`rounded-xl border p-4 sm:p-5 ${t.card}`}>
        <h3 className={`font-semibold ${t.textH} mb-3`}>Modo Sandbox / LLMs</h3>
        <p className={`${t.text} text-sm mb-2`}>
          Los endpoints marcados con "Probar" ejecutan llamadas reales a la API usando tu API key actual. Para entrenar modelos de IA o probar sin riesgo:
        </p>
        <ul className={`text-sm ${t.textMuted} space-y-1 list-disc list-inside`}>
          <li>Usa <code className={`px-1 rounded ${t.badge} text-xs`}>/api/health</code> y <code className={`px-1 rounded ${t.badge} text-xs`}>/api/nit/lookup</code> — son de solo lectura</li>
          <li>Crea una API key con rol <code className={`px-1 rounded ${t.badge} text-xs`}>VIEWER</code> para limitar operaciones</li>
          <li>Usa el <a href="https://github.com/ANGELBERRIOS23/OpenFEL" className="text-accent hover:underline">MCP server</a> para conectar agentes de IA directamente a OpenFEL</li>
          <li>La skill de Claude Code está en <code className={`px-1 rounded ${t.badge} text-xs`}>~/.claude/skills/openfel/SKILL.md</code></li>
        </ul>
      </div>
    </div>
  );
}
