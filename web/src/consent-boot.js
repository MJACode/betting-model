// Consent page for connecting an AI assistant (signalbase-ai.com/oauth/consent).
//
// Supabase Auth's OAuth 2.1 server sends the member here with
// ?authorization_id=... The page signs them in with an email code (the same
// sign-in as the app), shows which app is asking and where it will return
// them, checks they are a paying or comped member (public.mcp_my_status),
// records their acceptance of the AI assistant terms
// (public.mcp_accept_terms), then approves or denies the request through
// Supabase Auth and follows the redirect it returns.
//
// Everything the OAuth client supplies (its name, its redirect address) is
// shown with textContent, never as HTML: with dynamic client registration
// anyone can register an app under any name, which is also why the return
// address is shown in bold beside the name.
//
// CONFIG (supabaseUrl, supabaseAnonKey, termsVersion) is prepended by build.py.

(function () {
  "use strict";

  var AUTH = CONFIG.supabaseUrl + "/auth/v1";
  var REST = CONFIG.supabaseUrl + "/rest/v1";
  var KEY = CONFIG.supabaseAnonKey;
  var TOKEN_KEY = "sb-consent-token";

  var params = new URLSearchParams(window.location.search);
  var authorizationId = params.get("authorization_id") || "";
  var details = null;
  var email = "";

  function $(id) { return document.getElementById(id); }

  function show(id) {
    ["state-loading", "state-email", "state-code", "state-consent", "state-ineligible", "state-error", "state-done"]
      .forEach(function (s) { $(s).hidden = s !== id; });
  }

  function fail(message) {
    $("error-text").textContent = message;
    show("state-error");
  }

  function token() {
    try { return sessionStorage.getItem(TOKEN_KEY) || ""; } catch (e) { return ""; }
  }

  function setToken(value) {
    try {
      if (value) sessionStorage.setItem(TOKEN_KEY, value);
      else sessionStorage.removeItem(TOKEN_KEY);
    } catch (e) { /* private mode: keep it for this page only */ }
    window.__consentToken = value || "";
  }

  function jwt() { return token() || window.__consentToken || ""; }

  function call(method, url, body, withUser) {
    var headers = { apikey: KEY, "Content-Type": "application/json" };
    if (withUser) headers.Authorization = "Bearer " + jwt();
    return fetch(url, { method: method, headers: headers, body: body ? JSON.stringify(body) : undefined })
      .then(function (r) {
        return r.text().then(function (t) {
          var data = null;
          try { data = t ? JSON.parse(t) : null; } catch (e) { data = null; }
          if (!r.ok) {
            var err = new Error((data && (data.msg || data.message || data.error_description || data.error)) || ("HTTP " + r.status));
            err.status = r.status;
            throw err;
          }
          return data;
        });
      });
  }

  function hostOf(uri) {
    try { return new URL(uri).host; } catch (e) { return uri || "an unknown address"; }
  }

  function go(url) {
    show("state-done");
    window.location.assign(url);
  }

  function loadRequest() {
    if (!/^[A-Za-z0-9_-]{8,100}$/.test(authorizationId)) {
      fail("This link is missing its connection request. Start again from your AI assistant.");
      return;
    }
    if (!jwt()) { show("state-email"); return; }
    show("state-loading");
    call("GET", AUTH + "/oauth/authorizations/" + encodeURIComponent(authorizationId), null, true)
      .then(function (d) {
        if (d && d.redirect_url && !d.authorization_id) { go(d.redirect_url); return; }
        details = d;
        return call("POST", REST + "/rpc/mcp_my_status", {}, true).then(function (status) {
          var name = (d.client && (d.client.name || d.client.client_name)) || "An app";
          var redirect = d.redirect_uri || (d.client && d.client.redirect_uri) || "";
          $("client-name").textContent = name;
          $("client-host").textContent = hostOf(redirect);
          $("who").textContent = (d.user && d.user.email) || email || "your account";
          if (!status || !status.eligible) {
            var text;
            if (status && status.entitlement === "trial") {
              text = "Connecting an AI assistant is for paying members. It unlocks automatically when your free trial becomes a paid subscription.";
            } else if (status && status.preview_only) {
              text = "This account can preview AI Assistant in the app, but connecting is for paying members.";
            } else {
              text = "Connecting an AI assistant is for paying Signal Base members.";
            }
            $("ineligible-text").textContent = text;
            show("state-ineligible");
            return;
          }
          if (status.unlimited) $("limit-line").textContent = "Founder account: no daily limit.";
          if (status.suspended) {
            $("ineligible-text").textContent = "AI assistant access is paused on this account. Contact Signal Base support.";
            show("state-ineligible");
            return;
          }
          show("state-consent");
        });
      })
      .catch(function (e) {
        if (e.status === 401 || e.status === 403) { setToken(""); show("state-email"); return; }
        fail("We couldn't load this request. It may have expired: start again from your AI assistant.");
      });
  }

  $("state-email").addEventListener("submit", function (ev) {
    ev.preventDefault();
    email = $("email").value.trim();
    if (!email) return;
    call("POST", AUTH + "/otp", { email: email, create_user: false })
      .then(function () {
        $("code-email").textContent = email;
        show("state-code");
        $("code").focus();
      })
      .catch(function () { fail("We couldn't send a code to that email. Use the email on your Signal Base account."); });
  });

  $("state-code").addEventListener("submit", function (ev) {
    ev.preventDefault();
    var code = $("code").value.trim();
    call("POST", AUTH + "/verify", { type: "email", email: email, token: code })
      .then(function (session) {
        if (!session || !session.access_token) throw new Error("no session");
        setToken(session.access_token);
        loadRequest();
      })
      .catch(function () {
        $("code").value = "";
        $("code").setAttribute("aria-invalid", "true");
        $("code").focus();
      });
  });

  $("code-back").addEventListener("click", function () { show("state-email"); });

  $("agree").addEventListener("change", function () { $("allow").disabled = !$("agree").checked; });

  function decide(action) {
    $("allow").disabled = true;
    $("deny").disabled = true;
    var first = action === "approve"
      ? call("POST", REST + "/rpc/mcp_accept_terms", {
          p_version: CONFIG.termsVersion,
          p_client: (details && details.client && (details.client.name || details.client.client_name)) || null
        }, true)
      : Promise.resolve();
    first
      .then(function () {
        return call("POST", AUTH + "/oauth/authorizations/" + encodeURIComponent(authorizationId) + "/consent",
          { action: action }, true);
      })
      .then(function (r) {
        if (r && r.redirect_url) go(r.redirect_url);
        else fail("The connection didn't complete. Start again from your AI assistant.");
      })
      .catch(function () { fail("The connection didn't complete. Start again from your AI assistant."); });
  }

  $("allow").addEventListener("click", function () { if ($("agree").checked) decide("approve"); });
  $("deny").addEventListener("click", function () { decide("deny"); });
  $("ineligible-close").addEventListener("click", function () { decide("deny"); });
  $("sign-out").addEventListener("click", function () { setToken(""); show("state-email"); });

  loadRequest();
})();
