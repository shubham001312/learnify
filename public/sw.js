const CACHE = "learnify-v2";
const PRECACHE = ["/", "/index.html", "/styles.css?v=5", "/src/app.js?v=5", "/manifest.webmanifest"];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE).then((c) => c.addAll(PRECACHE).catch(() => {})).then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k)))
    ).then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (event) => {
  const req = event.request;
  if (req.method !== "GET") return;
  const url = new URL(req.url);
  if (url.pathname.startsWith("/api") || url.hostname !== self.location.hostname) return;

  // Network-first so new deploys are picked up immediately; fall back to cache.
  event.respondWith(
    fetch(req)
      .then((res) => {
        const c = caches.open(CACHE);
        if (res && res.status === 200) c.then((cache) => cache.put(req, res.clone()));
        return res;
      })
      .catch(() => caches.match(req))
  );
});
