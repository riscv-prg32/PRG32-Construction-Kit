// Lets libraries that create <style> elements at run time (Monaco, Blockly) work under the
// kit's Content Security Policy without 'unsafe-inline' (ADR-0012, ADR-0013).
//
// The server puts a fresh random nonce in <meta name="csp-nonce"> and in the CSP header of the
// same page. Every <style> element created from now on gets that nonce, so the browser accepts
// it; styles injected any other way (for example into HTML text) are still refused.
// This file must load before Blockly and Monaco.
(function () {
  'use strict';
  const meta = document.querySelector('meta[name="csp-nonce"]');
  const nonce = meta ? meta.getAttribute('content') : '';
  if (!nonce) return;
  meta.setAttribute('content', '');  // keep it out of the page once read
  const createElement = Document.prototype.createElement;
  Document.prototype.createElement = function (tagName, options) {
    const element = createElement.call(this, tagName, options);
    if (String(tagName).toLowerCase() === 'style') element.nonce = nonce;
    return element;
  };
})();
