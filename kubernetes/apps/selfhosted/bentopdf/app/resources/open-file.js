/*
 * PWA file-handler shim for BentoPDF (not part of upstream).
 *
 * The web manifest declares /open as the file handler for .pdf. When the
 * installed PWA is launched by the OS with a file, this page receives it
 * through window.launchQueue, loads a BentoPDF tool in a same-origin iframe
 * and feeds the file to the tool's own <input type="file">.
 *
 * The tool defaults to the editor; /open?tool=<page> picks another one.
 * No inline script and no template literals: the site CSP is script-src
 * 'self' and Flux would try to substitute dollar-brace expressions.
 */
(function () {
  'use strict';

  var RETRY_MS = 250;
  var GIVE_UP_MS = 20000;

  var frame = document.getElementById('app');
  var tool = new URLSearchParams(window.location.search).get('tool') || 'edit-pdf';
  if (!/^[a-z0-9-]+$/.test(tool)) tool = 'edit-pdf';
  var toolUrl = '/' + tool;

  var pending = null; // files waiting to be handed to the tool
  var loaded = false; // the iframe document finished loading
  var consumed = false; // the current iframe document already received files
  var timer = null;

  function asPdf(file) {
    // BentoPDF filters on file.type, which the OS does not always provide.
    if (file.type === 'application/pdf') return file;
    return new File([file], file.name, {
      type: 'application/pdf',
      lastModified: file.lastModified,
    });
  }

  function isShown(doc, id) {
    var el = doc.getElementById(id);
    return el ? !el.classList.contains('hidden') : false;
  }

  // Cheap fingerprint of "the tool reacted to a file": BentoPDF shows its
  // loader (or an alert) synchronously, then fills the file list / viewer.
  function snapshot(doc) {
    var area = doc.getElementById('file-display-area');
    return [
      isShown(doc, 'loader-modal'),
      isShown(doc, 'alert-modal'),
      isShown(doc, 'embed-pdf-wrapper'),
      area ? area.childElementCount : 0,
    ].join('|');
  }

  // The editor renders below the upload box: bring it into view once it shows.
  function reveal(doc, deadline) {
    var viewer = doc.getElementById('embed-pdf-wrapper');
    if (!viewer || doc !== frame.contentDocument) return;
    if (!viewer.classList.contains('hidden') && !isShown(doc, 'loader-modal')) {
      viewer.style.scrollMarginTop = '80px'; // keep clear of the sticky header
      viewer.scrollIntoView({ block: 'start' });
      return;
    }
    if (Date.now() < deadline) {
      window.setTimeout(function () {
        reveal(doc, deadline);
      }, RETRY_MS);
    }
  }

  function inject(baseline, deadline) {
    timer = null;
    if (!pending) return;

    var win = frame.contentWindow;
    var doc;
    try {
      doc = frame.contentDocument;
    } catch (e) {
      return;
    }
    if (!win || !doc) return;

    var input = doc.getElementById('file-input') || doc.querySelector('input[type="file"]');
    if (input) {
      if (baseline === null) baseline = snapshot(doc);

      // The tool attaches its listeners asynchronously (after i18n loads),
      // so dispatch until the page visibly reacts, and never after that.
      if (snapshot(doc) === baseline) {
        var files = input.multiple ? pending : pending.slice(0, 1);
        var transfer = new win.DataTransfer();
        files.forEach(function (file) {
          transfer.items.add(file);
        });
        input.files = transfer.files;
        input.dispatchEvent(new win.Event('change', { bubbles: true }));
      }
      if (snapshot(doc) !== baseline) {
        pending = null;
        consumed = true;
        reveal(doc, Date.now() + GIVE_UP_MS);
        return;
      }
    }

    if (Date.now() < deadline) {
      timer = window.setTimeout(function () {
        inject(baseline, deadline);
      }, RETRY_MS);
    }
  }

  function start() {
    if (timer !== null) window.clearTimeout(timer);
    inject(null, Date.now() + GIVE_UP_MS);
  }

  function navigate() {
    loaded = false;
    consumed = false;
    frame.src = toolUrl;
  }

  frame.addEventListener('load', function () {
    loaded = true;
    consumed = false;
    if (pending) start();
  });

  if ('launchQueue' in window) {
    window.launchQueue.setConsumer(function (launch) {
      if (!launch.files || launch.files.length === 0) return;
      Promise.all(
        launch.files.map(function (handle) {
          return handle.getFile();
        })
      ).then(function (files) {
        pending = files.map(asPdf);
        document.title = files[0].name + ' - BentoPDF';
        // Reuse the freshly loaded tool, otherwise reload it for a clean state.
        if (loaded && !consumed) start();
        else if (loaded) navigate();
      });
    });
  }

  navigate();
})();
