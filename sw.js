const CACHE_NAME = "tiempo-montevideo-v1";
const APP_SHELL = [
  "./",
  "./index.html",
  "./manifest.webmanifest",
  "./icon-192.png",
  "./icon-512.png"
];

self.addEventListener("install", event => {
  event.waitUntil(
    caches.open(CACHE_NAME).then(cache => cache.addAll(APP_SHELL))
  );
  self.skipWaiting();
});

self.addEventListener("activate", event => {
  event.waitUntil(
    caches.keys().then(keys => Promise.all(
      keys.filter(key => key !== CACHE_NAME).map(key => caches.delete(key))
    ))
  );
  self.clients.claim();
});

self.addEventListener("fetch", event => {
  const request = event.request;
  const url = new URL(request.url);

  if (request.method !== "GET") return;

  // data.json siempre intenta la red primero para no congelar el tiempo actual.
  if (url.pathname.endsWith("/data.json")) {
    event.respondWith(
      fetch(request, { cache: "no-store" })
        .then(response => response)
        .catch(() => caches.match(request))
    );
    return;
  }

  // Navegación: red primero, con respaldo offline.
  if (request.mode === "navigate") {
    event.respondWith(
      fetch(request)
        .then(response => {
          const copy = response.clone();
          caches.open(CACHE_NAME).then(cache => cache.put("./index.html", copy));
          return response;
        })
        .catch(() => caches.match("./index.html"))
    );
    return;
  }

  // Recursos estáticos: caché primero.
  event.respondWith(
    caches.match(request).then(cached => cached || fetch(request))
  );
});
