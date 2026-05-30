(function () {
  'use strict';

  // Only run on authenticated pages
  if (!document.querySelector('meta[name="user-authenticated"]')) return;

  var SESSION_TIMEOUT_MIN = 720;  // 12 hours (matches PERMANENT_SESSION_LIFETIME)
  var WARN_BEFORE_MIN     = 5;    // show banner 5 min before expiry
  var CHECK_INTERVAL_MS   = 60000; // check every 60 s

  var loginTimestamp = Date.now();

  var _intervalId = setInterval(function () {
    var elapsedMin   = (Date.now() - loginTimestamp) / 60000;
    var remainingMin = SESSION_TIMEOUT_MIN - elapsedMin;

    if (remainingMin <= 0) {
      clearInterval(_intervalId);
      window.location.href =
        '/auth/login?next=' + encodeURIComponent(window.location.pathname);
      return;
    }

    if (remainingMin <= WARN_BEFORE_MIN && !window._bqSessionWarnShown) {
      window._bqSessionWarnShown = true;
      _showSessionWarning(Math.ceil(remainingMin));
    }
  }, CHECK_INTERVAL_MS);

  function _showSessionWarning(minLeft) {
    // Remove any existing banner first
    var existing = document.querySelector('.session-warn-banner');
    if (existing) existing.remove();

    var banner = document.createElement('div');
    banner.className = 'session-warn-banner';
    banner.setAttribute('role', 'alert');
    banner.innerHTML =
      '<span>Your session expires in ' + minLeft + ' min. / ستنتهي جلستك خلال ' + minLeft + ' د.</span>' +
      '<button class="bq-btn bq-btn--sm bq-btn--primary" onclick="bqExtendSession()" type="button">' +
      'Stay signed in / ابق مسجلاً' +
      '</button>';
    document.body.appendChild(banner);
  }

  window.bqExtendSession = function () {
    fetch('/auth/heartbeat', {
      method: 'POST',
      credentials: 'same-origin',
      headers: {
        'X-CSRFToken': _getCsrf(),
        'Content-Type': 'application/json',
      },
    }).then(function (r) {
      if (r.ok) {
        loginTimestamp = Date.now();
        window._bqSessionWarnShown = false;
        var b = document.querySelector('.session-warn-banner');
        if (b) b.remove();
      }
    }).catch(function () {
      // Network error — silently ignore; page reload will redirect to login
    });
  };

  function _getCsrf() {
    var m = document.querySelector('meta[name="csrf-token"]');
    return m ? m.getAttribute('content') : '';
  }
}());
