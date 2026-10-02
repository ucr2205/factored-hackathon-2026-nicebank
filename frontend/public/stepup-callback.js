// Keycloak redirects the step-up iframe here: hand the authorization response to the app that opened the dialog
// (same origin only). Opened on its own, it just goes home.
(function () {
  if (window.parent !== window) {
    window.parent.postMessage({ type: "nb-stepup", url: window.location.href }, window.location.origin);
  } else {
    window.location.replace("/");
  }
})();
