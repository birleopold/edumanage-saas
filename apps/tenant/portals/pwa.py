"""Small Django-only PWA helpers for EduManage."""
import json

from decouple import config
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, JsonResponse
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST

from .models import WebPushSubscription


SERVICE_WORKER_JS = r"""
const CACHE_NAME = "edumanage-static-v3";
const STATIC_ASSETS = [
  "/static/css/public-tailwind.css",
  "/static/css/edumanage-system.css",
  "/static/css/edumanage-legacy-pages.css",
  "/static/css/admin-module-actions.css",
  "/static/css/role-scope-clarity.css",
  "/static/css/mobile-pwa.css",
  "/static/css/django-only-utilities.css",
  "/static/js/edumanage-system.js",
  "/static/js/admin-module-actions.js",
  "/static/js/role-scope-clarity.js",
  "/static/js/mobile-bottom-nav.js",
  "/static/js/pwa-lite.js",
  "/static/js/alpine-lite.js",
  "/static/js/chart-lite.js",
  "/static/js/offline-attendance.js",
  "/static/img/pwa-icon.svg"
];

const OFFLINE_HTML = `<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Offline | EduManage</title><style>body{margin:0;font-family:system-ui,-apple-system,Segoe UI,sans-serif;background:#f8fafc;color:#0f172a;display:grid;min-height:100vh;place-items:center;padding:20px}.card{max-width:520px;background:#fff;border:1px solid #e2e8f0;border-radius:28px;padding:32px;box-shadow:0 24px 70px -45px rgba(15,23,42,.8)}.tag{font-size:12px;font-weight:900;text-transform:uppercase;letter-spacing:.18em;color:#2563eb}h1{margin:.5rem 0 0;font-size:28px}p{color:#475569;line-height:1.6}.btn{display:inline-flex;margin-top:16px;border-radius:14px;background:#2563eb;color:#fff;padding:12px 18px;text-decoration:none;font-weight:900}</style></head><body><main class="card"><p class="tag">EduManage offline</p><h1>You are offline</h1><p>School records are never cached as private pages. Reconnect to load them safely. Attendance drafts saved on this device will sync after you sign in and reconnect.</p><a class="btn" href="/">Try again</a></main></body></html>`;

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(CACHE_NAME).then((cache) => cache.addAll(STATIC_ASSETS).catch(() => null)));
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) => Promise.all(keys.filter((key) => key !== CACHE_NAME).map((key) => caches.delete(key))))
  );
  self.clients.claim();
});

function clearPrivateData() {
  const clearCaches = caches.keys().then((keys) => Promise.all(keys.map((key) => caches.delete(key))));
  const clearDrafts = new Promise((resolve) => {
    const deletion = indexedDB.deleteDatabase("edumanage-offline-v1");
    deletion.onsuccess = deletion.onerror = deletion.onblocked = () => resolve();
  });
  return Promise.all([clearCaches, clearDrafts]).then(() => caches.open(CACHE_NAME).then((cache) => cache.addAll(STATIC_ASSETS).catch(() => null)));
}

self.addEventListener("message", (event) => {
  if (!event.data || event.data.type !== "CLEAR_EDUMANAGE_PRIVATE_DATA") return;
  event.waitUntil(clearPrivateData());
});

self.addEventListener("fetch", (event) => {
  const request = event.request;
  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;
  if (/(^|\/)logout\/?$/.test(url.pathname)) event.waitUntil(clearPrivateData());
  if (request.method !== "GET") return;

  if (request.mode === "navigate") {
    event.respondWith(
      fetch(request, { cache: "no-store" }).catch(() => new Response(OFFLINE_HTML, { headers: { "Content-Type": "text/html; charset=utf-8", "Cache-Control": "no-store" } }))
    );
    return;
  }

  if (url.pathname.startsWith("/static/")) {
    event.respondWith(
      caches.match(request).then((cached) => cached || fetch(request).then((response) => {
        if (!response || !response.ok) return response;
        const copy = response.clone();
        caches.open(CACHE_NAME).then((cache) => cache.put(request, copy));
        return response;
      }))
    );
  }
});

self.addEventListener("push", (event) => {
  let payload = { title: "EduManage", body: "You have a new school notification." };
  try { if (event.data) payload = event.data.json(); } catch (error) {}
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
    response["Cache-Control"] = "no-store"
    return response


def manifest(request):
    return JsonResponse(
        {
            "name": "EduManage School System",
            "short_name": "EduManage",
            "description": "EduManage installable school management portal",
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


def _active_subscription_count(user):
    if not user.is_authenticated:
        return 0
    return WebPushSubscription.objects.filter(user=user, is_active=True).count()


def push_readiness(request):
    public_key = config("WEB_PUSH_PUBLIC_KEY", default="")
    return JsonResponse(
        {
            "service_worker": True,
            "push_api_ready": True,
            "vapid_public_key_configured": bool(public_key),
            "vapid_public_key": public_key,
            "subscription_storage_ready": True,
            "active_subscriptions": _active_subscription_count(request.user),
            "subscribe_url": "/pwa/push-subscribe/",
            "unsubscribe_url": "/pwa/push-unsubscribe/",
            "private_page_caching": False,
            "message": "Static PWA assets and push subscriptions are enabled. Authenticated school pages are never cached.",
        }
    )


@login_required
@require_POST
def push_subscribe(request):
    try:
        payload = json.loads(request.body.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({"ok": False, "error": "Invalid subscription payload."}, status=400)

    endpoint = payload.get("endpoint")
    keys = payload.get("keys") or {}
    if not endpoint:
        return JsonResponse({"ok": False, "error": "Missing endpoint."}, status=400)
    if not keys.get("p256dh") or not keys.get("auth"):
        return JsonResponse({"ok": False, "error": "Missing browser push keys."}, status=400)

    subscription, _created = WebPushSubscription.objects.update_or_create(
        endpoint=endpoint,
        defaults={
            "user": request.user,
            "p256dh_key": keys.get("p256dh", ""),
            "auth_key": keys.get("auth", ""),
            "user_agent": request.META.get("HTTP_USER_AGENT", ""),
            "is_active": True,
            "last_seen_at": timezone.now(),
            "last_error": "",
        },
    )
    return JsonResponse(
        {
            "ok": True,
            "subscription_id": subscription.pk,
            "active_subscriptions": _active_subscription_count(request.user),
        }
    )


@login_required
@require_POST
def push_unsubscribe(request):
    try:
        payload = json.loads(request.body.decode("utf-8")) if request.body else {}
    except (json.JSONDecodeError, UnicodeDecodeError):
        payload = {}
    endpoint = payload.get("endpoint")
    queryset = WebPushSubscription.objects.filter(user=request.user, is_active=True)
    if endpoint:
        queryset = queryset.filter(endpoint=endpoint)
    now = timezone.now()
    updated = queryset.update(is_active=False, last_seen_at=now, updated_at=now)
    return JsonResponse({"ok": True, "disabled": updated, "active_subscriptions": _active_subscription_count(request.user)})
