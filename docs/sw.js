// Primero busca la versión nueva en internet (máx. 4 s); sin señal abre la guardada.
const C = "precios-hn-v3";
self.addEventListener("install", e => { self.skipWaiting(); });
self.addEventListener("activate", e => e.waitUntil(
  caches.keys().then(ks => Promise.all(ks.filter(k => k !== C).map(k => caches.delete(k)))).then(() => self.clients.claim())));
self.addEventListener("fetch", e => {
  const u = new URL(e.request.url);
  if (e.request.method !== "GET" || u.origin !== location.origin) return;
  e.respondWith(caches.open(C).then(async c => {
    const hit = await c.match(e.request);
    const red = fetch(e.request, {cache: "no-cache"}).then(r => { if (r.ok) c.put(e.request, r.clone()); return r; });
    if (!hit) return red;
    return Promise.race([red, new Promise((_, no) => setTimeout(no, 4000))]).catch(() => hit);
  }));
});
