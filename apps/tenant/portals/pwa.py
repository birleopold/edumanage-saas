"""Small no-build PWA helpers for EduManage.

Everything here is plain Django + static browser APIs. No Node, no npm and no
front-end build step are required.
"""

from django.conf import settings
from django.http import HttpResponse, JsonResponse
from django.views.decorators.cache import never_cache


SERVICE_WORKER_JS = r"""
const CACHE_NAME = "edumanage-static-v1";
const STATIC_ASSETS = [
  "/static/css/edumanage-system.css",
  "/static/css/edumanage-legacy-pages.css",
  "/static/css/admin-module-actions.css",
  "/static/css/role-scope-clarity.css",
  "/static/css/mobile-pwa.css",
  "/static/js/edumanage-system.js",
  "/static/js/admin-module-actions.js",
  "/static/js/role-scope-clarity.js",
  "/static/js/mobile-bottom-nav.js",
  "/static/js/pwa-lite.js",
  "/static/img/pwa-icon.svg"
];

const OFFLINE_HTML = `<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Offline | EduManage</title><style>body{margin:0;font-family:system-ui,-apple-system,Segoe UI,sans-serif;background:#f8fafc;color:#0f172a;display:grid;min-height:100vh;place-items:center;padding:20px}.card{max-width:520px;background:#fff;border:1px solid #e2e8f0;border-radius:28px;padding:32px;box-shadow:0 24px 70px -45px rgba(15,23,42,.8)}.tag{font-size:12px;font-weight:900;text-transform:uppercase;letter-spacing:.18em;color:#2563eb}h1{margin:.5rem 0 0;font-size:28px}p{color:#475569;line-height:1.6}.btn{display:inline-flex;margin-top:16px;border-radius:14px;background:#2563eb;color:#fff;padding:12px 18px;text-decoration:none;font-weight:900}</style></head><body><main class="card"><p class="tag">EduManage offline</p><h1>You are offline</h1><p>The app is still installed, but this school data needs an internet connection. Reconnect and try again.</p><a class="btn" href="/">Try again</a></main></body></html>`;

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(STATIC_ASSETS).catch(() => null))
  );
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) => Promise.all(keys.filter((key) => key !== CACHE_NAME).map((key) => caches.delete(key))))
  );
  self.clients.claim();
});

self.addEventListener("fetch", (event) => {
  const request = event.request;
  if (request.method !== "GET") return;
  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;

  if (request.mode === "navigate") {
    event.respondWith(
      fetch(request).catch(() => new Response(OFFLINE_HTML, { headers: { "Content-Type": "text/html; charset=utf-8" } }))
    );
    return;
  }

  if (url.pathname.startsWith("/static/")) {
    event.respondWith(
      caches.match(request).then((cached) => cached || fetch(request).then((response) => {
        const copy = response.clone();
        caches.open(CACHE_NAME).then((cache) => cache.put(request, copy));
        return response;
      }))
    );
  }
});

self.addEventListener("push", (event) => {
  let payload = { title: "EduManage", body: "You have a new school notification." };
  try {
    if (event.data) payload = event.data.json();
  } catch (error) {}
  event.waitUntil(
    self.registration.showNotification(payload.title || "EduManage", {
      body: payload.body || "You have a new school notification.",
      icon: "/static/img/pwa-icon.svg",
      badge: "/static/img/pwa-icon.svg",
      data: payload.url || "/"
    })
  );
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const target = event.notification.data || "/";
  event.waitUntil(clients.openWindow(target));
});
"""


@never_cache
def service_worker(request):
    response = HttpResponse(SERVICE_WORKER_JS, content_type="application/javascript; charset=utf-8")
    response["Service-Worker-Allowed"] = "/"
    return response


def manifest(request):
    return JsonResponse(
        {
            "name": "EduManage School System",
            "short_name": "EduManage",
            "description": "EduManage mobile school management portal",
            "start_url": "/",
            "scope": "/",
            "display": "standalone",
            "orientation": "portrait-primary",
            "background_color": "#f8fafc",
            "theme_color": "#2563eb",
            "categories": ["education", "productivity"],
            "icons": [
                {"src": "/static/img/pwa-icon.svg", "sizes": "any", "type": "image/svg+xml", "purpose": "any maskable"},
            ],
        }
    )


def push_readiness(request):
    public_key = getattr(settings, "WEB_PUSH_PUBLIC_KEY", "")
    return JsonResponse(
        {
            "service_worker": True,
            "push_api_ready": True,
            "vapid_public_key_configured": bool(public_key),
            "message": "Browser push APIs are prepared. Add a VAPID public key and subscription endpoint when server-side push delivery is enabled.",
        }
    )
