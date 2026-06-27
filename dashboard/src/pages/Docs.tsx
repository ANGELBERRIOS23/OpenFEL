import { useState, useEffect } from 'react';
import { Play, Copy, Check, ChevronDown, ChevronRight } from 'lucide-react';
import { useTheme } from '../lib/useThemeClasses';

interface Endpoint {
  method: string;
  path: string;
  role: string;
  desc: string;
  params?: { name: string; type: string; required?: boolean; desc: string }[];
  bodyExample?: string;
  responseExample?: string;
}

interface Section {
  name: string;
  endpoints: Endpoint[];
}

const sections: Section[] = [
  {
    name: 'Health',
    endpoints: [
      {
        method: 'GET', path: '/api/health', role: 'público',
        desc: 'Estado de los 4 servidores SAT (DNS, TLS, HTTP, latencia). No requiere API key.',
        responseExample: `{
  "farm3": { "status": "up", "latency_ms": 245 },
  "felav02": { "status": "up", "latency_ms": 312 },
  "felcons": { "status": "up", "latency_ms": 198 },
  "mobile": { "status": "up", "latency_ms": 156 }
}`,
      },
    ],
  },
  {
    name: 'NIT',
    endpoints: [
      {
        method: 'POST', path: '/api/nit/lookup', role: 'VIEWER',
        desc: 'Consultar nombre de un NIT en el Registro Tributario Unificado (RTU) de la SAT.',
        bodyExample: `{
  "account_nit": "120405237",
  "nit": "CF"
}`,
        responseExample: `{
  "nit": "CF",
  "nombre": "CONSUMIDOR FINAL",
  "estado": "ACTIVO"
}`,
      },
    ],
  },
  {
    name: 'DTE',
    endpoints: [
      {
        method: 'POST', path: '/api/dte/emit', role: 'OPERATOR',
        desc: 'Emitir un DTE. Soporta 15 regímenes fiscales por ítem: GENERAL, EXENTO, EXPORT, PEQ, NO_AFECTO, TURISMO_HOSPEDAJE, PETROLEO, TURISMO_PASAJES, TIMBRE_PRENSA, BOMBEROS, BEBIDAS_ALCOHOLICAS, TABACO, CEMENTO, BEBIDAS_NO_ALCOHOLICAS, TARIFA_PORTUARIA. Frases y complementos automáticos.',
        bodyExample: `{
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
}`,
        responseExample: `{
  "uuid": "F72BA9CD-0D79-4B1F-9453-0273B7D2EA88",
  "serie": "12345678",
  "numero": "226052895",
  "fecha_certificacion": "2026-06-27T10:30:00",
  "source": "fallback"
}`,
      },
      {
        method: 'POST', path: '/api/dte/annul', role: 'OPERATOR',
        desc: 'Anular un DTE por UUID. El nit_receptor DEBE coincidir con el receptor original — usar "CF" cuando la factura fue emitida a un NIT específico causará fallo silencioso.',
        bodyExample: `{
  "account_nit": "120405237",
  "uuid": "UUID-AQUI",
  "motivo": "Error en datos",
  "nit_receptor": "CF"
}`,
        responseExample: `{
  "uuid": "F72BA9CD-...",
  "estado": "OK",
  "source": "mobile"
}`,
      },
      {
        method: 'GET', path: '/api/dte/emitted', role: 'VIEWER',
        desc: 'Listar últimos DTEs emitidos (hasta 100).',
        params: [{ name: 'account_nit', type: 'string', required: true, desc: 'NIT de la cuenta emisora' }],
        responseExample: `{
  "total": 5,
  "items": [{ "uuid": "...", "tipo": "FACT", "fecha": "...", "total": 500.00 }],
  "source": "mobile"
}`,
      },
      {
        method: 'GET', path: '/api/dte/received', role: 'VIEWER',
        desc: 'Listar últimos DTEs recibidos (hasta 100).',
        params: [{ name: 'account_nit', type: 'string', required: true, desc: 'NIT de la cuenta' }],
      },
      {
        method: 'GET', path: '/api/dte/{uuid}/detail', role: 'VIEWER',
        desc: 'Detalle completo de un DTE por UUID.',
        params: [
          { name: 'account_nit', type: 'string', required: true, desc: 'NIT de la cuenta' },
          { name: 'uuid', type: 'string', required: true, desc: 'UUID del DTE (en la URL)' },
        ],
      },
      {
        method: 'GET', path: '/api/dte/{uuid}/pdf', role: 'VIEWER',
        desc: 'Descargar PDF oficial de SAT. nit_receptor debe coincidir con el de la factura original (CF da vacío si fue a un NIT).',
        params: [
          { name: 'account_nit', type: 'string', required: true, desc: 'NIT de la cuenta' },
          { name: 'nit_receptor', type: 'string', desc: 'NIT del receptor (default: CF)' },
        ],
      },
      {
        method: 'GET', path: '/api/dte/{uuid}/custom-pdf', role: 'VIEWER',
        desc: 'PDF personalizado con branding de la cuenta: logo, colores corporativos, teléfono, email, web y QR de verificación SAT.',
        params: [
          { name: 'account_nit', type: 'string', required: true, desc: 'NIT de la cuenta' },
          { name: 'nit_receptor', type: 'string', desc: 'NIT del receptor (default: CF)' },
        ],
      },
      {
        method: 'GET', path: '/api/dte/{uuid}/pos-receipt', role: 'VIEWER',
        desc: 'Recibo POS para impresoras térmicas. Formato blanco y negro con QR.',
        params: [
          { name: 'account_nit', type: 'string', required: true, desc: 'NIT de la cuenta' },
          { name: 'nit_receptor', type: 'string', desc: 'NIT del receptor (default: CF)' },
          { name: 'width', type: 'integer', desc: 'Ancho en mm: 58 o 80 (default: 80)' },
        ],
      },
      {
        method: 'GET', path: '/api/dte/{uuid}/xml', role: 'VIEWER',
        desc: 'Descargar XML del DTE. Si no hay XML firmado disponible, se reconstruye desde el detalle.',
        params: [
          { name: 'account_nit', type: 'string', required: true, desc: 'NIT de la cuenta' },
          { name: 'nit_receptor', type: 'string', desc: 'NIT del receptor (default: CF)' },
        ],
      },
    ],
  },
  {
    name: 'Cuentas',
    endpoints: [
      {
        method: 'GET', path: '/api/accounts', role: 'ADMIN',
        desc: 'Listar todas las cuentas SAT registradas.',
      },
      {
        method: 'POST', path: '/api/accounts', role: 'ADMIN',
        desc: 'Crear cuenta. Auto-detecta nombre y afiliación vía NIT lookup.',
        bodyExample: `{
  "nit": "120405237",
  "login_password": "...",
  "cert_password": "...",
  "preferred_api": "mixed",
  "affiliation": "GEN",
  "name": ""
}`,
      },
      {
        method: 'GET', path: '/api/accounts/{nit}', role: 'ADMIN',
        desc: 'Obtener detalle de una cuenta.',
      },
      {
        method: 'PATCH', path: '/api/accounts/{nit}', role: 'ADMIN',
        desc: 'Editar cuenta: contraseñas, modo API, afiliación, nombre, estado. Incluye branding para PDF personalizado.',
        bodyExample: `{
  "branding": {
    "color_primario": "#1a5276",
    "color_secundario": "#2e86c1",
    "telefono": "+502 3014 9000",
    "email": "contacto@empresa.com",
    "web": "empresa.com",
    "logo_b64": null
  }
}`,
      },
      {
        method: 'DELETE', path: '/api/accounts/{nit}', role: 'ADMIN',
        desc: 'Eliminar cuenta permanentemente.',
      },
    ],
  },
  {
    name: 'API Keys',
    endpoints: [
      {
        method: 'GET', path: '/api/keys', role: 'ADMIN',
        desc: 'Listar todas las API keys.',
      },
      {
        method: 'POST', path: '/api/keys', role: 'ADMIN',
        desc: 'Crear key. La key completa se muestra SOLO una vez.',
        bodyExample: `{
  "name": "Mi Key",
  "role": "VIEWER",
  "allowed_accounts": []
}`,
      },
      {
        method: 'PATCH', path: '/api/keys/{id}', role: 'ADMIN',
        desc: 'Actualizar key (nombre, rol, estado, cuentas permitidas).',
      },
      {
        method: 'DELETE', path: '/api/keys/{id}', role: 'ADMIN',
        desc: 'Revocar key (soft delete).',
      },
    ],
  },
  {
    name: 'Audit',
    endpoints: [
      {
        method: 'GET', path: '/api/logs', role: 'ADMIN',
        desc: 'Consultar log de auditoría.',
        params: [
          { name: 'action', type: 'string', desc: 'Filtrar por acción' },
          { name: 'account_nit', type: 'string', desc: 'Filtrar por cuenta' },
          { name: 'limit', type: 'integer', desc: 'Límite (default: 50)' },
          { name: 'offset', type: 'integer', desc: 'Offset para paginación' },
        ],
      },
    ],
  },
];

const allEndpoints = sections.flatMap((s, si) =>
  s.endpoints.map((ep, ei) => ({ ...ep, section: s.name, key: `${si}-${ei}` }))
);

function methodColor(m: string) {
  return m === 'GET' ? 'text-green-500' : m === 'POST' ? 'text-blue-500' :
    m === 'PATCH' ? 'text-amber-500' : m === 'DELETE' ? 'text-red-500' : '';
}

function methodBg(m: string, t: ReturnType<typeof useTheme>) {
  return m === 'GET' ? t.badgeGreen : m === 'POST' ? t.badgeBlue :
    m === 'PATCH' ? t.badgeAmber : m === 'DELETE' ? t.badgeRed : t.badge;
}

function buildPath(ep: typeof allEndpoints[0], paramValues: Record<string, string>) {
  let p = ep.path;
  for (const [k, v] of Object.entries(paramValues)) {
    p = p.replace(`{${k}}`, v || `{${k}}`);
  }
  const qp = (ep.params || []).filter(pr => !ep.path.includes(`{${pr.name}}`));
  if (qp.length > 0) {
    const qs = qp.map(pr => `${pr.name}=${paramValues[pr.name] || ''}`).join('&');
    p += (p.includes('?') ? '&' : '?') + qs;
  }
  return p;
}

export default function Docs() {
  const t = useTheme();
  const [selected, setSelected] = useState(0);
  const [openSections, setOpenSections] = useState<Record<string, boolean>>(
    Object.fromEntries(sections.map(s => [s.name, true]))
  );
  const [paramValues, setParamValues] = useState<Record<string, string>>({});
  const [bodyValue, setBodyValue] = useState('');
  const [response, setResponse] = useState<string | null>(null);
  const [status, setStatus] = useState(0);
  const [responseTime, setResponseTime] = useState(0);
  const [loading, setLoading] = useState(false);
  const [copied, setCopied] = useState('');
  const [showMobileSidebar, setShowMobileSidebar] = useState(false);

  const ep = allEndpoints[selected];
  const apiKey = sessionStorage.getItem('openfel_key') || '';

  useEffect(() => {
    setBodyValue(ep.bodyExample || '');
    setParamValues({});
    setResponse(null);
    setStatus(0);
  }, [selected]);

  function toggleSection(name: string) {
    setOpenSections(prev => ({ ...prev, [name]: !prev[name] }));
  }

  async function send() {
    setLoading(true);
    setResponse(null);
    setStatus(0);
    const t0 = performance.now();
    try {
      const url = buildPath(ep, paramValues);
      const opts: RequestInit = {
        method: ep.method,
        headers: {
          'X-API-Key': apiKey,
          ...(bodyValue && ep.method !== 'GET' ? { 'Content-Type': 'application/json' } : {}),
        },
      };
      if (bodyValue && ep.method !== 'GET') opts.body = bodyValue;
      const res = await fetch(url, opts);
      const elapsed = Math.round(performance.now() - t0);
      setStatus(res.status);
      setResponseTime(elapsed);

      const ct = res.headers.get('content-type') || '';
      if (ct.includes('json')) {
        const data = await res.json();
        setResponse(JSON.stringify(data, null, 2));
      } else if (ct.includes('pdf') || ct.includes('xml') || ct.includes('octet')) {
        const blob = await res.blob();
        setResponse(`[Binary: ${blob.size} bytes — ${ct}]`);
        if (blob.size > 0) {
          const a = document.createElement('a');
          a.href = URL.createObjectURL(blob);
          a.download = url.includes('pdf') ? 'download.pdf' : url.includes('xml') ? 'download.xml' : 'download.bin';
          a.click();
        }
      } else {
        setResponse(await res.text() || '[Empty response]');
      }
    } catch (err: any) {
      setStatus(0);
      setResponseTime(Math.round(performance.now() - t0));
      setResponse(`Network error: ${err.message}`);
    } finally {
      setLoading(false);
    }
  }

  function copyCurl() {
    const url = buildPath(ep, paramValues);
    let cmd = `curl -X ${ep.method}`;
    cmd += ` \\\n  -H "X-API-Key: \${API_KEY}"`;
    if (bodyValue && ep.method !== 'GET') {
      cmd += ` \\\n  -H "Content-Type: application/json"`;
      cmd += ` \\\n  -d '${bodyValue.replace(/\n\s*/g, ' ')}'`;
    }
    cmd += ` \\\n  http://localhost:8000${url}`;
    navigator.clipboard.writeText(cmd);
    setCopied('curl');
    setTimeout(() => setCopied(''), 2000);
  }

  function copyResponse_() {
    if (response) {
      navigator.clipboard.writeText(response);
      setCopied('resp');
      setTimeout(() => setCopied(''), 2000);
    }
  }

  const statusColor = status >= 200 && status < 300 ? t.badgeGreen :
    status >= 400 ? t.badgeRed : status >= 300 ? t.badgeAmber : t.badge;

  return (
    <div className="flex gap-0 -mx-4 md:-mx-6 -mt-4 md:-mt-6 min-h-[calc(100vh-3rem)]">
      {/* Mobile endpoint selector */}
      <button onClick={() => setShowMobileSidebar(!showMobileSidebar)}
        className={`lg:hidden fixed bottom-4 right-4 z-40 px-4 py-2 rounded-full shadow-lg bg-accent text-white text-sm cursor-pointer`}>
        Endpoints
      </button>

      {/* LEFT: Endpoint tree */}
      <aside className={`${t.isDark ? 'bg-[#1e293b]' : 'bg-white'} border-r ${t.border} w-56 shrink-0 overflow-y-auto
        ${showMobileSidebar ? 'fixed inset-y-0 left-56 z-40 lg:static' : 'hidden lg:block'}`}>
        <div className={`px-3 py-3 border-b ${t.border}`}>
          <p className={`text-xs font-semibold uppercase tracking-wider ${t.textMuted}`}>API Reference</p>
        </div>
        <nav className="py-1">
          {sections.map(section => {
            const isOpen = openSections[section.name];
            return (
              <div key={section.name}>
                <button onClick={() => toggleSection(section.name)}
                  className={`w-full flex items-center gap-1.5 px-3 py-2 text-xs font-semibold cursor-pointer ${t.textMuted} hover:${t.textH}`}>
                  {isOpen ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
                  {section.name}
                </button>
                {isOpen && section.endpoints.map((_ep, ei) => {
                  const flatIdx = allEndpoints.findIndex(
                    ae => ae.section === section.name && ae.path === _ep.path && ae.method === _ep.method
                  );
                  const isActive = selected === flatIdx;
                  const shortPath = _ep.path.replace('/api/', '/').replace(/\{[^}]+\}/g, ':id');
                  return (
                    <button key={ei} onClick={() => { setSelected(flatIdx); setShowMobileSidebar(false); }}
                      className={`w-full flex items-center gap-2 pl-7 pr-3 py-1.5 text-xs cursor-pointer transition-colors
                        ${isActive ? 'bg-accent/15 text-accent' : `${t.text} hover:bg-accent/5`}`}>
                      <span className={`font-mono font-bold w-10 text-left text-[10px] ${methodColor(_ep.method)}`}>
                        {_ep.method}
                      </span>
                      <span className="truncate font-mono">{shortPath}</span>
                    </button>
                  );
                })}
              </div>
            );
          })}
        </nav>

        {/* Roles & info */}
        <div className={`border-t ${t.border} px-3 py-3 space-y-2`}>
          <p className={`text-[10px] font-semibold uppercase tracking-wider ${t.textMuted}`}>Roles</p>
          <div className="space-y-1">
            <div className="flex items-center gap-2 text-[10px]">
              <span className={`px-1.5 py-0.5 rounded ${t.badge}`}>VIEWER</span>
              <span className={t.textMuted}>Solo lectura</span>
            </div>
            <div className="flex items-center gap-2 text-[10px]">
              <span className={`px-1.5 py-0.5 rounded ${t.badgeBlue}`}>OPERATOR</span>
              <span className={t.textMuted}>+ Emitir/anular</span>
            </div>
            <div className="flex items-center gap-2 text-[10px]">
              <span className={`px-1.5 py-0.5 rounded ${t.badgePurple}`}>ADMIN</span>
              <span className={t.textMuted}>+ Cuentas/keys</span>
            </div>
          </div>
          <p className={`text-[10px] font-semibold uppercase tracking-wider ${t.textMuted} pt-2`}>API Modes</p>
          <div className="space-y-1 text-[10px]">
            <div><span className={`font-mono ${t.textH}`}>mixed</span> <span className={t.textMuted}>— inteligente</span></div>
            <div><span className={`font-mono ${t.textH}`}>mobile</span> <span className={t.textMuted}>— rápida, 12h</span></div>
            <div><span className={`font-mono ${t.textH}`}>web</span> <span className={t.textMuted}>— completa, 25min</span></div>
          </div>
        </div>
      </aside>

      {/* CENTER: Documentation */}
      <div className="flex-1 overflow-y-auto p-4 md:p-6 min-w-0">
        <div className="max-w-2xl">
          {/* Title */}
          <h1 className={`text-xl md:text-2xl font-bold ${t.textH} mb-2`}>
            {ep.section}: {ep.path.split('/').pop()?.replace(/[{}?]/g, '') || ep.path}
          </h1>

          {/* Method + URL */}
          <div className={`flex items-center gap-2 mb-4 p-3 rounded-lg border ${t.card}`}>
            <span className={`px-2 py-0.5 rounded text-xs font-mono font-bold ${methodBg(ep.method, t)}`}>
              {ep.method}
            </span>
            <code className={`text-sm font-mono ${t.textH} break-all`}>{ep.path}</code>
            <span className={`ml-auto px-2 py-0.5 rounded text-xs ${t.badge}`}>{ep.role}</span>
          </div>

          {/* Description */}
          <p className={`${t.text} text-sm mb-6 leading-relaxed`}>{ep.desc}</p>

          {/* Auth */}
          <div className="mb-6">
            <h3 className={`text-sm font-semibold ${t.textH} mb-2`}>Autenticación</h3>
            <div className={`p-3 rounded-lg border ${t.card} text-xs`}>
              {ep.role === 'público' ? (
                <span className={t.textMuted}>No requiere autenticación</span>
              ) : (
                <div className="flex items-center gap-2">
                  <span className={t.textMuted}>Header:</span>
                  <code className={`font-mono ${t.textH}`}>X-API-Key: ofel_k1_...</code>
                </div>
              )}
            </div>
          </div>

          {/* Parameters */}
          {ep.params && ep.params.length > 0 && (
            <div className="mb-6">
              <h3 className={`text-sm font-semibold ${t.textH} mb-2`}>Parámetros</h3>
              <div className={`rounded-lg border overflow-hidden ${t.card}`}>
                {ep.params.map((p, i) => (
                  <div key={i} className={`flex items-start gap-3 p-3 text-xs ${i > 0 ? `border-t ${t.borderSub}` : ''}`}>
                    <div className="w-32 shrink-0">
                      <code className={`font-mono font-semibold ${t.textH}`}>{p.name}</code>
                      {p.required && <span className="text-red-400 ml-1">*</span>}
                      <div className={`${t.textMuted} mt-0.5`}>{p.type}</div>
                    </div>
                    <span className={t.text}>{p.desc}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Request body */}
          {ep.bodyExample && (
            <div className="mb-6">
              <h3 className={`text-sm font-semibold ${t.textH} mb-2`}>Request Body</h3>
              <pre className={`text-xs p-3 rounded-lg overflow-x-auto ${t.codeBg}`}>
                {ep.bodyExample}
              </pre>
            </div>
          )}

          {/* Response example */}
          {ep.responseExample && (
            <div className="mb-6">
              <div className="flex items-center gap-3 mb-2">
                <h3 className={`text-sm font-semibold ${t.textH}`}>Response</h3>
                <span className={`px-2 py-0.5 rounded text-xs ${t.badgeGreen}`}>200</span>
                <span className={`text-xs ${t.textMuted}`}>application/json</span>
              </div>
              <pre className={`text-xs p-3 rounded-lg overflow-x-auto ${t.codeBg}`}>
                {ep.responseExample}
              </pre>
            </div>
          )}

          {/* Tax regimes info (show only for emit endpoint) */}
          {ep.path === '/api/dte/emit' && (
            <div className="mb-6">
              <h3 className={`text-sm font-semibold ${t.textH} mb-2`}>Regímenes fiscales por ítem</h3>
              <p className={`${t.textMuted} text-xs mb-3`}>
                Cada ítem puede tener su propio régimen. Las frases y complementos se generan automáticamente.
              </p>
              <div className={`rounded-lg border overflow-hidden ${t.card}`}>
                {[
                  ['GENERAL', 'IVA 12% (incluido en precio)', t.badgeGreen],
                  ['EXENTO', 'Exento de IVA (MontoImpuesto=0)', t.badgeBlue],
                  ['EXPORT', 'Exportación (con complemento automático)', t.badgePurple],
                  ['PEQ', 'Pequeño contribuyente (sin impuestos)', t.badgeAmber],
                  ['NO_AFECTO', 'No afecto a impuesto', t.badge],
                  ['TURISMO_HOSPEDAJE', 'IVA 12% + INGUAT 10%', t.badgeRed],
                  ['PETROLEO', 'IVA + Petróleo (default: diésel Q1.30/gal). Sub-códigos: _1 a _10', t.badge],
                  ['TURISMO_PASAJES', 'IVA + Pasajes aéreos $30. Sub-códigos: _1 aéreo, _2 marítimo, _3 exento', t.badge],
                  ['TIMBRE_PRENSA', 'IVA + Timbre de prensa 0.5%', t.badge],
                  ['BOMBEROS', 'IVA + Bomberos 2%', t.badge],
                  ['BEBIDAS_ALCOHOLICAS', 'IVA + Alcohol (default: cerveza 6%). Sub-códigos: _1, _2, _6', t.badge],
                  ['TABACO', 'IVA + Tabaco (fábrica 100% o sugerido 75%)', t.badge],
                  ['CEMENTO', 'IVA + Cemento Q1.50/bolsa', t.badge],
                  ['BEBIDAS_NO_ALCOHOLICAS', 'IVA + No alcohólicas (default: Q0.18). Sub-códigos: _1 a _5', t.badge],
                  ['TARIFA_PORTUARIA', 'IVA + Tarifa portuaria $0.05', t.badge],
                ].map(([name, desc, badge], i) => (
                  <div key={i} className={`flex items-center gap-3 px-3 py-2 text-xs ${i > 0 ? `border-t ${t.borderSub}` : ''}`}>
                    <span className={`px-2 py-0.5 rounded font-mono ${badge}`}>{name}</span>
                    <span className={t.text}>{desc}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* RIGHT: Playground panel */}
      <aside className={`${t.isDark ? 'bg-[#1a2332]' : 'bg-slate-50'} border-l ${t.border} w-[380px] shrink-0 overflow-y-auto hidden xl:flex xl:flex-col`}>
        {/* Auth */}
        <div className={`px-4 py-3 border-b ${t.border}`}>
          <div className="flex items-center gap-2 mb-2">
            <span className={`text-[10px] font-semibold uppercase tracking-wider ${t.textMuted}`}>Auth</span>
          </div>
          <div className={`flex items-center gap-2 px-2 py-1.5 rounded border text-xs font-mono ${t.input}`}>
            <span className={t.textMuted}>Token :</span>
            <span className={t.textH}>{apiKey ? `${apiKey.slice(0, 16)}...` : '(login first)'}</span>
          </div>
        </div>

        {/* Parameters */}
        <div className={`px-4 py-3 border-b ${t.border}`}>
          <span className={`text-[10px] font-semibold uppercase tracking-wider ${t.textMuted}`}>Parameters</span>
          <div className="mt-2 space-y-2">
            {(ep.params || []).map(p => (
              <div key={p.name}>
                <label className={`text-[10px] ${t.textMuted} flex items-center gap-1`}>
                  {p.name}{p.required && <span className="text-red-400">*</span>}
                  <span className={`ml-auto ${t.textXs}`}>{p.type}</span>
                </label>
                <input value={paramValues[p.name] || ''} placeholder={p.desc}
                  onChange={e => setParamValues(prev => ({ ...prev, [p.name]: e.target.value }))}
                  className={`w-full px-2 py-1 mt-0.5 border rounded text-xs font-mono ${t.input}`} />
              </div>
            ))}
            {ep.path.includes('{uuid}') && (
              <div>
                <label className={`text-[10px] ${t.textMuted}`}>uuid <span className="text-red-400">*</span></label>
                <input value={paramValues['uuid'] || ''} placeholder="UUID del DTE"
                  onChange={e => setParamValues(prev => ({ ...prev, uuid: e.target.value }))}
                  className={`w-full px-2 py-1 mt-0.5 border rounded text-xs font-mono ${t.input}`} />
              </div>
            )}
            {ep.path.includes('{nit}') && !ep.params?.find(p => p.name === 'nit') && (
              <div>
                <label className={`text-[10px] ${t.textMuted}`}>nit <span className="text-red-400">*</span></label>
                <input value={paramValues['nit'] || ''} placeholder="NIT de la cuenta"
                  onChange={e => setParamValues(prev => ({ ...prev, nit: e.target.value }))}
                  className={`w-full px-2 py-1 mt-0.5 border rounded text-xs font-mono ${t.input}`} />
              </div>
            )}
            {ep.path.includes('{id}') && (
              <div>
                <label className={`text-[10px] ${t.textMuted}`}>id <span className="text-red-400">*</span></label>
                <input value={paramValues['id'] || ''} placeholder="ID del recurso"
                  onChange={e => setParamValues(prev => ({ ...prev, id: e.target.value }))}
                  className={`w-full px-2 py-1 mt-0.5 border rounded text-xs font-mono ${t.input}`} />
              </div>
            )}
          </div>
        </div>

        {/* Body */}
        {ep.method !== 'GET' && (
          <div className={`px-4 py-3 border-b ${t.border}`}>
            <span className={`text-[10px] font-semibold uppercase tracking-wider ${t.textMuted}`}>Body</span>
            <textarea value={bodyValue} onChange={e => setBodyValue(e.target.value)}
              rows={Math.min(Math.max((bodyValue || '').split('\n').length, 3), 12)}
              className={`w-full mt-2 px-2 py-1.5 border rounded text-xs font-mono ${t.input}`} />
          </div>
        )}

        {/* Send button */}
        <div className={`px-4 py-3 border-b ${t.border}`}>
          <button onClick={send} disabled={loading}
            className="w-full flex items-center justify-center gap-2 px-4 py-2 bg-accent hover:bg-accent-hover text-white rounded-lg text-sm font-semibold disabled:opacity-50 cursor-pointer">
            <Play size={14} /> {loading ? 'Enviando...' : 'Send API Request'}
          </button>
        </div>

        {/* Curl */}
        <div className={`px-4 py-3 border-b ${t.border}`}>
          <div className="flex items-center justify-between mb-2">
            <span className={`text-[10px] font-semibold uppercase tracking-wider ${t.textMuted}`}>Request Sample · curl</span>
            <button onClick={copyCurl} className={`text-[10px] cursor-pointer ${t.textMuted} hover:text-accent`}>
              {copied === 'curl' ? <Check size={10} /> : <Copy size={10} />}
            </button>
          </div>
          <pre className={`text-[10px] p-2 rounded overflow-x-auto leading-relaxed ${t.codeBg}`}>
            {`curl -X ${ep.method} \\\n  -H "X-API-Key: \${API_KEY}" \\\n  http://localhost:8000${buildPath(ep, paramValues)}`}
            {bodyValue && ep.method !== 'GET' ? ` \\\n  -H "Content-Type: application/json" \\\n  -d '...'` : ''}
          </pre>
        </div>

        {/* Response */}
        <div className="px-4 py-3 flex-1">
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center gap-2">
              <span className={`text-[10px] font-semibold uppercase tracking-wider ${t.textMuted}`}>
                {response !== null ? 'Response' : 'Response Example'}
              </span>
              {status > 0 && (
                <>
                  <span className={`px-1.5 py-0.5 rounded text-[10px] font-mono font-bold ${statusColor}`}>{status}</span>
                  <span className={`text-[10px] ${t.textMuted}`}>{responseTime}ms</span>
                </>
              )}
            </div>
            {response && (
              <button onClick={copyResponse_} className={`text-[10px] cursor-pointer ${t.textMuted} hover:text-accent`}>
                {copied === 'resp' ? <Check size={10} /> : <Copy size={10} />}
              </button>
            )}
          </div>
          <pre className={`text-[10px] p-2 rounded overflow-x-auto max-h-80 overflow-y-auto leading-relaxed ${t.codeBg}`}>
            {loading ? 'Loading...' : response || ep.responseExample || '// Click "Send API Request" to see response'}
          </pre>
        </div>
      </aside>

      {/* Mobile/tablet: playground below docs (shown when no xl) */}
      <div className="xl:hidden fixed bottom-4 left-1/2 -translate-x-1/2 z-30">
        {/* The mobile playground is accessible via the existing TryPanel in the docs center */}
      </div>
    </div>
  );
}
