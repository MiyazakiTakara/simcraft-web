/**
 * error-reporter.js
 * Przechwytuje niezłapane błędy JS i wysyła je do /admin/api/client-error.
 * Ładowany jako pierwszy skrypt (zaraz po inline session-init w index.html).
 */
(function () {
  var ENDPOINT = '/admin/api/client-error';
  var RATE_LIMIT = 10;          // max błędów na sesję
  var _sent = 0;

  function send(payload) {
    if (_sent >= RATE_LIMIT) return;
    _sent++;
    try {
      navigator.sendBeacon
        ? navigator.sendBeacon(ENDPOINT, new Blob([JSON.stringify(payload)], { type: 'application/json' }))
        : fetch(ENDPOINT, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload), keepalive: true });
    } catch (_) {}
  }

  window.onerror = function (message, source, lineno, colno, error) {
    send({
      type:    'error',
      message: String(message).slice(0, 500),
      source:  source  || null,
      line:    lineno  || null,
      col:     colno   || null,
      stack:   error && error.stack ? String(error.stack).slice(0, 2000) : null,
      url:     window.location.href,
      ts:      new Date().toISOString(),
    });
    return false; // nie blokuj domyślnego logowania w konsoli
  };

  window.addEventListener('unhandledrejection', function (event) {
    var reason = event.reason;
    var message = reason instanceof Error ? reason.message : String(reason);
    var stack   = reason instanceof Error && reason.stack ? String(reason.stack).slice(0, 2000) : null;
    send({
      type:    'unhandledrejection',
      message: message.slice(0, 500),
      source:  null,
      line:    null,
      col:     null,
      stack:   stack,
      url:     window.location.href,
      ts:      new Date().toISOString(),
    });
  });
})();
