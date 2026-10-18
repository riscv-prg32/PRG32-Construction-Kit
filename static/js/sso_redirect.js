// Sends the single-sign-on form right away (templates/sso_redirect.html); the button is the fallback.
(function () {
  const form = document.getElementById('ssoForm');
  if (form) form.submit();
})();
