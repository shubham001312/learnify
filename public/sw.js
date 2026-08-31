const CACHE = "learnify-v57";
const PRECACHE = ["/", "/index.html", "/styles.css?v=57", "/src/app.js?v=57", "/manifest.webmanifest"];

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

  event.respondWith((async () => {
    try {
      const res = await fetch(req);
      // Cache a copy in the background. Clone immediately and never let
      // caching errors affect the response we return to the page.
      if (res && res.status === 200) {
        try {
          const copy = res.clone();
          const cache = await caches.open(CACHE);
          await cache.put(req, copy);
        } catch (_) { /* ignore cache failures */ }
      }
      return res;
    } catch (err) {
      const cached = await caches.match(req);
      if (cached) return cached;
      if (req.mode === "navigate") {
        const shell = await caches.match("/index.html");
        if (shell) return shell;
      }
      return new Response("", { status: 504, statusText: "Offline" });
    }
  })());
});
