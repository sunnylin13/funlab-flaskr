/*
 * FunLab global CSRF bootstrap (ADR-016 D2-c)
 * =============================================
 *
 * The server-side CSRFProtect (funlab-flaskr) validates POST/PUT/PATCH/DELETE
 * requests against the `X-CSRFToken` / `X-CSRF-Token` header (flask-wtf native
 * support).  Every base template injects
 *
 *     <meta name="csrf-token" content="{{ csrf_token() }}">
 *
 * and loads this script so that *all* existing JS submitters work unchanged:
 * polling_notifications.js, plugin_management.html fetch()s,
 * fundmgr portfolio/performance/benchmark/ffn `xhr.open('POST')`,
 * quotesvcs templates, and any future fetch/XHR call.
 *
 * Same-origin policy: the header is only injected for same-origin requests
 * (relative URLs, or absolute URLs with the same host), so third-party
 * endpoints never receive the token.
 *
 * Turbo (if present) already picks up the meta tag natively — nothing to do.
 */
(function () {
    'use strict';

    function csrfToken() {
        var meta = document.querySelector('meta[name="csrf-token"]');
        return meta ? meta.getAttribute('content') : '';
    }

    function sameOrigin(url) {
        try {
            var u = new URL(url, window.location.href);
            return u.origin === window.location.origin;
        } catch (e) {
            // Relative or malformed → treat as same-origin (fetch will resolve
            // relative URLs against this page anyway).
            return true;
        }
    }

    var _fetch = window.fetch ? window.fetch.bind(window) : null;
    if (_fetch) {
        window.fetch = function (input, init) {
            init = init || {};
            var method = (init.method || (input && input.method) || 'GET')
                .toUpperCase();
            if (method !== 'GET' && method !== 'HEAD' && method !== 'OPTIONS') {
                var url = (typeof input === 'string' || input instanceof URL)
                    ? String(input) : (input && input.url) || window.location.href;
                if (sameOrigin(url)) {
                    var token = csrfToken();
                    if (token) {
                        var headers = new Headers(init.headers ||
                            (input && input.headers) || {});
                        if (!headers.has('X-CSRFToken')) {
                            headers.set('X-CSRFToken', token);
                        }
                        init = Object.assign({}, init, { headers: headers });
                    }
                }
            }
            return _fetch(input, init);
        };
    }

    var _xhrOpen = XMLHttpRequest.prototype.open;
    var _xhrSend = XMLHttpRequest.prototype.send;
    XMLHttpRequest.prototype.open = function (method, url) {
        this.__csrfMethod = String(method || 'GET').toUpperCase();
        this.__csrfUrl = url;
        return _xhrOpen.apply(this, arguments);
    };
    XMLHttpRequest.prototype.send = function () {
        var method = this.__csrfMethod || 'GET';
        if (method !== 'GET' && method !== 'HEAD' && method !== 'OPTIONS' &&
                sameOrigin(this.__csrfUrl || window.location.href)) {
            var token = csrfToken();
            if (token) {
                try {
                    this.setRequestHeader('X-CSRFToken', token);
                } catch (e) {
                    // setRequestHeader must be called after open() and before
                    // send(); errors here must never break the request.
                }
            }
        }
        return _xhrSend.apply(this, arguments);
    };
})();
