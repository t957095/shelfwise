/* ShelfWise Service Worker - Offline support */
const CACHE_NAME = 'shelfwise-v1';
const STATIC_ASSETS = [
    '/app/',
    '/app/index.html',
    '/app/styles.css',
    '/app/app.js',
];

self.addEventListener('install', (e) => {
    e.waitUntil(
        caches.open(CACHE_NAME).then((cache) => cache.addAll(STATIC_ASSETS))
    );
    self.skipWaiting();
});

self.addEventListener('activate', (e) => {
    e.waitUntil(
        caches.keys().then((keys) =>
            Promise.all(keys.filter((k) => k !== CACHE_NAME).map((k) => caches.delete(k)))
        )
    );
    self.clients.claim();
});

self.addEventListener('fetch', (e) => {
    const { request } = e;
    // Only cache static assets and API GETs
    if (request.method !== 'GET') return;
    if (request.url.includes('/api/')) {
        // Network-first for API
        e.respondWith(
            fetch(request)
                .then((res) => {
                    if (res.ok) {
                        const clone = res.clone();
                        caches.open(CACHE_NAME).then((cache) => cache.put(request, clone));
                    }
                    return res;
                })
                .catch(() => caches.match(request))
        );
    } else if (STATIC_ASSETS.some((url) => request.url.includes(url.replace('/app/', '')))) {
        // Cache-first for static assets
        e.respondWith(caches.match(request).then((res) => res || fetch(request)));
    }
});
