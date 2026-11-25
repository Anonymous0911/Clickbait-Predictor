// Single place for fetch: same-origin (Vite proxies to Django) + CSRF header.
function csrfToken() {
  const match = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
  return match ? decodeURIComponent(match[1]) : '';
}

// One shared in-flight request, so simultaneous POSTs don't each fetch a token.
let csrfPending = null;
function ensureCsrf() {
  if (csrfToken()) return Promise.resolve();
  csrfPending ??= fetch('/api/auth/csrf', { credentials: 'same-origin' }).finally(() => { csrfPending = null; });
  return csrfPending;
}

export async function api(path, { method = 'GET', form, json } = {}) {
  const headers = {};
  let body;
  if (form) body = form;
  else if (json !== undefined) {
    headers['Content-Type'] = 'application/json';
    body = JSON.stringify(json);
  }
  if (method !== 'GET') {
    // Cookie can be missing if the mount-time csrf call failed or hasn't finished.
    try { await ensureCsrf(); } catch { /* the request below will surface the real error */ }
    headers['X-CSRFToken'] = csrfToken();
  }

  const response = await fetch(path, { method, headers, body, credentials: 'same-origin' });
  if (response.status === 204) return null;
  let payload = null;
  try { payload = await response.json(); } catch { /* non-JSON body */ }
  if (!response.ok) throw new Error(payload?.detail || 'Something went wrong.');
  return payload;
}
