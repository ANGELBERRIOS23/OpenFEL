const BASE = '/api';

function getKey(): string {
  return sessionStorage.getItem('openfel_key') || '';
}

export function setKey(key: string) {
  sessionStorage.setItem('openfel_key', key);
}

export function clearKey() {
  sessionStorage.removeItem('openfel_key');
}

export function hasKey(): boolean {
  return !!getKey();
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      'X-API-Key': getKey(),
      ...options.headers,
    },
  });
  if (res.status === 401) {
    clearKey();
    window.location.href = '/';
    throw new Error('Unauthorized');
  }
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `HTTP ${res.status}`);
  }
  if (res.status === 204) return undefined as T;
  return res.json();
}

export const api = {
  health: () => request<any>('/health'),

  keys: {
    list: () => request<any[]>('/keys'),
    create: (data: any) => request<any>('/keys', { method: 'POST', body: JSON.stringify(data) }),
    update: (id: number, data: any) => request<any>(`/keys/${id}`, { method: 'PATCH', body: JSON.stringify(data) }),
    revoke: (id: number) => request<void>(`/keys/${id}`, { method: 'DELETE' }),
  },

  accounts: {
    list: () => request<any[]>('/accounts'),
    create: (data: any) => request<any>('/accounts', { method: 'POST', body: JSON.stringify(data) }),
    get: (nit: string) => request<any>(`/accounts/${nit}`),
    update: (nit: string, data: any) => request<any>(`/accounts/${nit}`, { method: 'PATCH', body: JSON.stringify(data) }),
    deactivate: (nit: string) => request<void>(`/accounts/${nit}`, { method: 'DELETE' }),
  },

  nit: {
    lookup: (account_nit: string, nit: string) =>
      request<any>('/nit/lookup', { method: 'POST', body: JSON.stringify({ account_nit, nit }) }),
  },

  dte: {
    emit: (data: any) => request<any>('/dte/emit', { method: 'POST', body: JSON.stringify(data) }),
    annul: (data: any) => request<any>('/dte/annul', { method: 'POST', body: JSON.stringify(data) }),
    emitted: (account_nit: string) => request<any>(`/dte/emitted?account_nit=${account_nit}`),
    received: (account_nit: string) => request<any>(`/dte/received?account_nit=${account_nit}`),
    detail: (uuid: string, account_nit: string) => request<any>(`/dte/${uuid}/detail?account_nit=${account_nit}`),
    downloadPdf: async (uuid: string, account_nit: string, nit_receptor: string = 'CF') => {
      const res = await fetch(`${BASE}/dte/${uuid}/pdf?account_nit=${account_nit}&nit_receptor=${nit_receptor}`, {
        headers: { 'X-API-Key': getKey() },
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const blob = await res.blob();
      if (blob.size === 0) throw new Error('PDF vacío — verificar NIT receptor');
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url; a.download = `${uuid}.pdf`; a.click();
      URL.revokeObjectURL(url);
    },
    downloadXml: async (uuid: string, account_nit: string, nit_receptor: string = 'CF') => {
      const res = await fetch(`${BASE}/dte/${uuid}/xml?account_nit=${account_nit}&nit_receptor=${nit_receptor}`, {
        headers: { 'X-API-Key': getKey() },
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const blob = await res.blob();
      if (blob.size === 0) throw new Error('XML no disponible');
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url; a.download = `${uuid}.xml`; a.click();
      URL.revokeObjectURL(url);
    },
    downloadCustomPdf: async (uuid: string, account_nit: string, nit_receptor: string = 'CF') => {
      const res = await fetch(`${BASE}/dte/${uuid}/custom-pdf?account_nit=${account_nit}&nit_receptor=${nit_receptor}`, {
        headers: { 'X-API-Key': getKey() },
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const blob = await res.blob();
      if (blob.size === 0) throw new Error('Custom PDF vacío');
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url; a.download = `${uuid}_custom.pdf`; a.click();
      URL.revokeObjectURL(url);
    },
    downloadPosReceipt: async (uuid: string, account_nit: string, nit_receptor: string = 'CF', width: number = 80) => {
      const res = await fetch(`${BASE}/dte/${uuid}/pos-receipt?account_nit=${account_nit}&nit_receptor=${nit_receptor}&width=${width}`, {
        headers: { 'X-API-Key': getKey() },
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const blob = await res.blob();
      if (blob.size === 0) throw new Error('Recibo POS vacío');
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url; a.download = `${uuid}_receipt.pdf`; a.click();
      URL.revokeObjectURL(url);
    },
  },

  logs: {
    list: (params?: Record<string, string>) => {
      const qs = params ? '?' + new URLSearchParams(params).toString() : '';
      return request<any[]>(`/logs${qs}`);
    },
  },
};
