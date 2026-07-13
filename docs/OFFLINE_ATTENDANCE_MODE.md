# Offline Attendance Mode

Teachers can use Roll Call and the full Take Attendance page from the installed PWA when the internet drops.

## How it works

- Teachers open a Roll Call or Take Attendance page while online.
- The service worker caches that visited attendance page and the local static assets it needs.
- If the connection drops, teachers keep marking learners on that page.
- Saving while offline stores the latest class/date roll call on the device in `localStorage`.
- When the browser comes back online, the queued attendance save replays through the normal Django endpoint.

## Sync behavior

Offline saves are keyed by offering and date, so repeated offline saves for the same class/date replace the local queued copy instead of creating duplicates. The full attendance page stores both status and note values. The server side uses the existing attendance session and student uniqueness rules, so replaying the same class/date/student updates the existing row.

## Operational notes

- No Node, npm, CDN, or background build step is required.
- The queue is device-local. Teachers should use the same device until the sync status says the roll call is synced.
- A visited Roll Call or Take Attendance page can be reopened offline from the PWA cache. A class/date that has never been opened still needs internet for the first load.
