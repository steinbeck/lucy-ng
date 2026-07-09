(function () {
  'use strict';

  var STATUS_URL     = '/api/status';
  var STRUCTURES_URL = '/api/structures';
  var LOG_URL        = '/api/log';
  var CARBON_URL      = '/api/tables/carbon';
  var HSQC_URL        = '/api/tables/hsqc';
  var HMBC_URL        = '/api/tables/hmbc';
  var COSY_URL        = '/api/tables/cosy';
  var CONSTRAINTS_URL = '/api/tables/constraints';
  var REFRESH_MS     = 3000;

  // Track last-seen SMILES per index to avoid SVG flicker (D-10)
  var lastSmiles = {};

  // ------------------------------------------------------------------
  // refreshStatus
  // ------------------------------------------------------------------
  function refreshStatus() {
    fetch(STATUS_URL)
      .then(function (r) { return r.json(); })
      .then(function (data) { renderStatus(data); })
      .catch(function (e) { console.warn('status fetch failed:', e); });
  }

  function renderStatus(data) {
    var state = data.state || 'waiting';

    // State badge
    var badgeClass = 'badge-waiting';
    if (state === 'running')  { badgeClass = 'badge-running'; }
    if (state === 'complete') { badgeClass = 'badge-complete'; }
    if (state === 'error')    { badgeClass = 'badge-error'; }

    var stateEl = document.getElementById('status-state');
    var badge = document.createElement('span');
    badge.className = 'badge ' + badgeClass;
    badge.textContent = state;
    stateEl.textContent = '';
    stateEl.appendChild(badge);

    // Iteration
    var iterEl = document.getElementById('status-iter');
    iterEl.textContent = (data.iteration != null)
      ? 'Iteration ' + data.iteration : '';

    // Active phase
    var phaseEl = document.getElementById('status-phase');
    phaseEl.textContent = data.active_phase ? data.active_phase : '';

    // Elapsed
    var elapsedEl = document.getElementById('status-elapsed');
    if (data.elapsed_s != null) {
      elapsedEl.textContent = formatElapsed(data.elapsed_s);
    } else {
      elapsedEl.textContent = '';
    }
  }

  function formatElapsed(s) {
    var h = Math.floor(s / 3600);
    var m = Math.floor((s % 3600) / 60);
    var sec = s % 60;
    if (h > 0) {
      return h + 'h ' + pad(m) + 'm ' + pad(sec) + 's';
    }
    if (m > 0) {
      return m + 'm ' + pad(sec) + 's';
    }
    return sec + 's';
  }

  function pad(n) { return n < 10 ? '0' + n : '' + n; }

  // ------------------------------------------------------------------
  // refreshStructures
  // ------------------------------------------------------------------
  function refreshStructures() {
    fetch(STRUCTURES_URL)
      .then(function (r) { return r.json(); })
      .then(function (data) { renderStructures(data); })
      .catch(function (e) { console.warn('structures fetch failed:', e); });
  }

  function renderStructures(data) {
    var grid = document.getElementById('structure-grid');
    var hint = document.getElementById('structure-hint');

    var structures = data.structures || [];
    var total = (data.total != null) ? data.total : structures.length;

    if (structures.length === 0) {
      // Show waiting message (textContent only — XSS guard)
      var waiting = document.getElementById('structure-waiting');
      if (!waiting) {
        waiting = document.createElement('div');
        waiting.id = 'structure-waiting';
        grid.appendChild(waiting);
      }
      waiting.textContent = 'Waiting for candidates...';
      hint.textContent = '';
      return;
    }

    // Remove waiting placeholder if present
    var waitingEl = document.getElementById('structure-waiting');
    if (waitingEl) { waitingEl.remove(); }

    // Build or update tiles
    structures.forEach(function (item) {
      var idx = item.index;
      var tileId = 'tile-' + idx;
      var tile = document.getElementById(tileId);

      if (!tile) {
        // Create new tile
        tile = document.createElement('div');
        tile.className = 'tile';
        tile.id = tileId;

        var img = document.createElement('img');
        img.id = 'img-' + idx;
        img.alt = 'Structure ' + idx;

        var labelEl = document.createElement('div');
        labelEl.className = 'tile-label';
        labelEl.id = 'label-' + idx;

        tile.appendChild(img);
        tile.appendChild(labelEl);
        grid.appendChild(tile);
      }

      // Re-fetch SVG only if SMILES changed (D-10: no flicker).
      // Direct compare — a `|| null` coercion made empty-string SMILES
      // ("" || null === null) re-fetch forever every tick.
      var smiles = item.smiles || '';
      if (smiles !== lastSmiles[idx]) {
        var img2 = document.getElementById('img-' + idx);
        if (img2) {
          img2.src = '/api/structure/' + idx + '.svg?t=' + Date.now();
        }
        lastSmiles[idx] = smiles;
      }

      // Render label (rank / MAE / quality) — D-09: HTML around tile, not in SVG
      var labelDiv = document.getElementById('label-' + idx);
      if (labelDiv) {
        var rankText  = (item.rank  != null) ? 'Rank ' + item.rank : '';
        var maeText   = (item.mae   != null) ? 'MAE ' + item.mae.toFixed(2) + ' ppm' : '';
        var qualText  = item.quality || '';
        var parts = [rankText, maeText, qualText].filter(Boolean);

        // Build label lines safely with textContent nodes
        labelDiv.textContent = '';
        if (parts.length > 0) {
          var rankSpan = document.createElement('span');
          rankSpan.className = 'tile-rank';
          rankSpan.textContent = rankText || ('Index ' + idx);
          labelDiv.appendChild(rankSpan);

          if (maeText || qualText) {
            labelDiv.appendChild(document.createTextNode(' '));
            var qualSpan = document.createElement('span');
            qualSpan.className = 'tile-quality';
            qualSpan.textContent = [maeText, qualText].filter(Boolean).join(' · ');
            labelDiv.appendChild(qualSpan);
          }
        } else {
          labelDiv.textContent = 'Index ' + idx;
        }
      }
    });

    // "+N more" hint when total exceeds shown
    if (total > structures.length) {
      hint.textContent = '+' + (total - structures.length) + ' more candidate'
        + (total - structures.length !== 1 ? 's' : '') + ' not shown';
    } else {
      hint.textContent = total + ' candidate' + (total !== 1 ? 's' : '');
    }
  }

  // ------------------------------------------------------------------
  // renderLog  — markdown-to-DOM block parser (LOG-01 / D-02)
  //
  // Converts the closed CASE-PROGRESS.md subset (headings, bold labels,
  // inline code, pipe-tables, hr, bullets, fenced code) into DOM nodes.
  // NEVER builds an HTML string / assigns the DOM's dangerous markup-injection
  // property — every leaf is set via textContent/createTextNode. This satisfies
  // the phase's mandatory XSS acceptance criterion by construction (T-93-01).
  // ------------------------------------------------------------------
  function renderLog(rawText, container) {
    // Clear existing children via removeChild loop, not markup-injection
    // (preserves D-13 scroll-restore contract at the refreshLog() call site).
    while (container.firstChild) { container.removeChild(container.firstChild); }

    var lines = rawText.split('\n');
    var i = 0;
    while (i < lines.length) {
      var line = lines[i];

      // Fenced code block: ```...```
      if (/^```/.test(line)) {
        var codeLines = [];
        i++;
        while (i < lines.length && !/^```/.test(lines[i])) { codeLines.push(lines[i]); i++; }
        i++; // skip closing fence
        var pre = document.createElement('pre');
        var codeEl = document.createElement('code');
        codeEl.textContent = codeLines.join('\n');
        pre.appendChild(codeEl);
        container.appendChild(pre);
        continue;
      }

      // Heading: #, ##, ### (only levels used by the coordinator's writer)
      var headingMatch = /^(#{1,3})\s+(.*)$/.exec(line);
      if (headingMatch) {
        var tag = 'h' + headingMatch[1].length;
        var hEl = document.createElement(tag);
        appendInline(hEl, headingMatch[2]);
        container.appendChild(hEl);
        i++;
        continue;
      }

      // Horizontal rule
      if (/^---+\s*$/.test(line)) {
        container.appendChild(document.createElement('hr'));
        i++;
        continue;
      }

      // Pipe table: header row + separator row (e.g. |---|---|) required before
      // treating as a table — avoids false positives on stray '|' chars in body text.
      if (/^\|.*\|\s*$/.test(line) && i + 1 < lines.length
          && /^\|[\s:|-]+\|\s*$/.test(lines[i + 1])) {
        var headerCells = line.split('|').slice(1, -1).map(function (s) { return s.trim(); });
        i += 2; // skip header + separator
        var rows = [];
        while (i < lines.length && /^\|.*\|\s*$/.test(lines[i])) {
          rows.push(lines[i].split('|').slice(1, -1).map(function (s) { return s.trim(); }));
          i++;
        }
        container.appendChild(buildTable(headerCells, rows));
        continue;
      }

      // Bullet list item: - text  (used in ### Team Models)
      if (/^-\s+/.test(line)) {
        var ul = document.createElement('ul');
        while (i < lines.length && /^-\s+/.test(lines[i])) {
          var li = document.createElement('li');
          appendInline(li, lines[i].replace(/^-\s+/, ''));
          ul.appendChild(li);
          i++;
        }
        container.appendChild(ul);
        continue;
      }

      // Blank line: skip
      if (line.trim() === '') { i++; continue; }

      // Default: paragraph line (covers **Field:** value lines)
      var p = document.createElement('p');
      appendInline(p, line);
      container.appendChild(p);
      i++;
    }
  }

  function buildTable(headerCells, rows) {
    var table = document.createElement('table');
    var thead = document.createElement('thead');
    var headRow = document.createElement('tr');
    headerCells.forEach(function (cell) {
      var th = document.createElement('th');
      appendInline(th, cell);
      headRow.appendChild(th);
    });
    thead.appendChild(headRow);
    table.appendChild(thead);

    var tbody = document.createElement('tbody');
    rows.forEach(function (rowCells) {
      var tr = document.createElement('tr');
      rowCells.forEach(function (cell) {
        var td = document.createElement('td');
        appendInline(td, cell);
        tr.appendChild(td);
      });
      tbody.appendChild(tr);
    });
    table.appendChild(tbody);
    return table;
  }

  // Inline tokenizer: splits on **bold** and `code` spans, appends child nodes
  // via textContent / createElement ONLY — never markup-injection.
  function appendInline(parent, text) {
    var tokenRe = /\*\*(.+?)\*\*|`(.+?)`/g;
    var lastIndex = 0;
    var match;
    while ((match = tokenRe.exec(text)) !== null) {
      if (match.index > lastIndex) {
        parent.appendChild(document.createTextNode(text.slice(lastIndex, match.index)));
      }
      if (match[1] !== undefined) {
        var strong = document.createElement('strong');
        strong.textContent = match[1];
        parent.appendChild(strong);
      } else {
        var code = document.createElement('code');
        code.textContent = match[2];
        parent.appendChild(code);
      }
      lastIndex = tokenRe.lastIndex;
    }
    if (lastIndex < text.length) {
      parent.appendChild(document.createTextNode(text.slice(lastIndex)));
    }
  }

  // ------------------------------------------------------------------
  // refreshLog  — D-13: preserve scroll unless user is at bottom
  // ------------------------------------------------------------------
  function refreshLog() {
    var logEl = document.getElementById('log-panel'); // now a <div>, was <pre>
    // Capture scroll position BEFORE the update
    var atBottom = (logEl.scrollHeight - logEl.scrollTop) <= (logEl.clientHeight + 5);

    fetch(LOG_URL)
      .then(function (r) { return r.json(); })
      .then(function (data) {
        var content = data.content || '';
        if (!content) {
          while (logEl.firstChild) { logEl.removeChild(logEl.firstChild); }
          logEl.appendChild(document.createTextNode('Waiting for log data...'));
        } else {
          renderLog(content, logEl);
        }
        if (atBottom) {
          logEl.scrollTop = logEl.scrollHeight;
        }
        // (else: preserve current scrollTop — browser keeps it unchanged)
      })
      .catch(function (e) { console.warn('log fetch failed:', e); });
  }

  // ------------------------------------------------------------------
  // Tables tab — shared helpers (Phase 94: TBL-01/02/03)
  // ------------------------------------------------------------------

  // Compact intensity formatting (D-04 — exact algorithm, UI-SPEC verbatim).
  function formatIntensity(v) {
    if (v == null) { return ''; }
    var abs = Math.abs(v);
    if (abs >= 1e6) { return (v / 1e6).toFixed(1) + 'M'; }
    if (abs >= 1e3) { return (v / 1e3).toFixed(1) + 'K'; }
    return String(Math.trunc(v));
  }

  // "Yes"/"No" for booleans — never raw true/false (mirrors the TBL-03
  // ring_exclusion_enabled rule, applied consistently to boolean QC columns).
  function formatBool(v) {
    if (v == null) { return ''; }
    return v ? 'Yes' : 'No';
  }

  // Defensive string coercion for table cells — null/undefined -> ''.
  function cellText(v) {
    if (v == null) { return ''; }
    return String(v);
  }

  // Per-table caption (D-05): "{note} — {counts}", dropping the dangling
  // em-dash when note is absent/empty. textContent-only assignment (D-02).
  function setCaption(el, note, counts) {
    if (!el) { return; }
    el.textContent = note ? (note + ' — ' + counts) : counts;
  }

  function clearChildren(el) {
    while (el.firstChild) { el.removeChild(el.firstChild); }
  }

  // Per-table "waiting for data" state (SC4 — independent per table).
  function showTableWaiting(bodyEl, captionEl, message) {
    clearChildren(bodyEl);
    if (captionEl) { captionEl.textContent = ''; }
    var waiting = document.createElement('div');
    waiting.className = 'table-waiting';
    waiting.textContent = message;
    bodyEl.appendChild(waiting);
  }

  // ------------------------------------------------------------------
  // refreshCarbon / renderCarbon — TBL-01
  // ------------------------------------------------------------------
  function refreshCarbon() {
    fetch(CARBON_URL)
      .then(function (r) { return r.json(); })
      .then(function (data) { renderCarbon(data); })
      .catch(function (e) { console.warn('carbon fetch failed:', e); });
  }

  function renderCarbon(data) {
    var bodyEl = document.getElementById('table-carbon-body');
    var captionEl = document.getElementById('table-carbon-caption');
    var rows = (data && data.rows) || [];

    if (!data || data.state !== 'ok' || rows.length === 0) {
      showTableWaiting(bodyEl, captionEl, 'Waiting for ¹³C signal data...');
      return;
    }

    var counts = data.counts || {};
    setCaption(
      captionEl,
      data.note,
      cellText(counts.formula) + ', DBE ' + cellText(counts.dbe) + ', ' + cellText(counts.solvent)
    );

    var tableRows = rows.map(function (row) {
      return [
        cellText(row.ppm),
        cellText(row.mult),
        cellText(row.nC),
        cellText(row.assignment),
        cellText(row.confidence),
      ];
    });
    var table = buildTable(
      ['δC (ppm)', 'Mult', 'nC', 'Assignment', 'Confidence'],
      tableRows
    );
    table.className = 'data-table';
    clearChildren(bodyEl);
    bodyEl.appendChild(table);
  }

  // ------------------------------------------------------------------
  // refreshHsqc / renderHsqc — TBL-02
  // ------------------------------------------------------------------
  function refreshHsqc() {
    fetch(HSQC_URL)
      .then(function (r) { return r.json(); })
      .then(function (data) { renderHsqc(data); })
      .catch(function (e) { console.warn('hsqc fetch failed:', e); });
  }

  function renderHsqc(data) {
    var bodyEl = document.getElementById('table-hsqc-body');
    var captionEl = document.getElementById('table-hsqc-caption');
    var rows = (data && data.rows) || [];

    if (!data || data.state !== 'ok' || rows.length === 0) {
      showTableWaiting(bodyEl, captionEl, 'Waiting for HSQC correlation data...');
      return;
    }

    var counts = data.counts || {};
    setCaption(captionEl, data.note, cellText(counts.count) + ' correlations');

    var tableRows = rows.map(function (row) {
      return [
        cellText(row.carbon_ppm),
        cellText(row.proton_ppm),
        formatBool(row.matched_real_carbon),
        formatBool(row.one_bond),
        formatIntensity(row.intensity),
      ];
    });
    var table = buildTable(
      ['δC (ppm)', 'δH (ppm)', 'Matched Real C', '1-Bond', 'Intensity'],
      tableRows
    );
    table.className = 'data-table';
    clearChildren(bodyEl);
    bodyEl.appendChild(table);
  }

  // ------------------------------------------------------------------
  // refreshHmbc / renderHmbc — TBL-02 (D-03: show all rows, colour by flag)
  // ------------------------------------------------------------------
  var HMBC_FLAG_CLASS = {
    ok: 'row-ok',
    potential_4J: 'row-potential-4j',
    '1J_artifact': 'row-1j-artifact',
  };

  function refreshHmbc() {
    fetch(HMBC_URL)
      .then(function (r) { return r.json(); })
      .then(function (data) { renderHmbc(data); })
      .catch(function (e) { console.warn('hmbc fetch failed:', e); });
  }

  function renderHmbc(data) {
    var bodyEl = document.getElementById('table-hmbc-body');
    var captionEl = document.getElementById('table-hmbc-caption');
    var rows = (data && data.rows) || [];

    if (!data || data.state !== 'ok' || rows.length === 0) {
      showTableWaiting(bodyEl, captionEl, 'Waiting for HMBC correlation data...');
      return;
    }

    var counts = data.counts || {};
    setCaption(
      captionEl,
      data.note,
      cellText(counts.kept_count) + ' kept of ' + cellText(counts.raw_count)
    );

    var tableRows = rows.map(function (row) {
      return [
        cellText(row.carbon_ppm),
        cellText(row.carbon_ppm_observed),
        cellText(row.proton_ppm),
        cellText(row.flag),
        formatIntensity(row.intensity),
      ];
    });
    var table = buildTable(
      ['δC (ppm)', 'δC observed (ppm)', 'δH (ppm)', 'Flag', 'Intensity'],
      tableRows
    );
    table.className = 'data-table';

    // D-03: colour every kept row by its `flag` value — post-process only,
    // matching the fetched row order; never fork buildTable, no markup-injection.
    var trs = table.querySelectorAll('tbody tr');
    for (var i = 0; i < trs.length; i++) {
      var flag = rows[i] && rows[i].flag;
      var cls = HMBC_FLAG_CLASS[flag];
      if (cls) { trs[i].className = cls; }
    }

    clearChildren(bodyEl);
    bodyEl.appendChild(table);
  }

  // ------------------------------------------------------------------
  // refreshCosy / renderCosy — TBL-02
  // ------------------------------------------------------------------
  function refreshCosy() {
    fetch(COSY_URL)
      .then(function (r) { return r.json(); })
      .then(function (data) { renderCosy(data); })
      .catch(function (e) { console.warn('cosy fetch failed:', e); });
  }

  function renderCosy(data) {
    var bodyEl = document.getElementById('table-cosy-body');
    var captionEl = document.getElementById('table-cosy-caption');
    var rows = (data && data.rows) || [];

    if (!data || data.state !== 'ok' || rows.length === 0) {
      showTableWaiting(bodyEl, captionEl, 'Waiting for COSY correlation data...');
      return;
    }

    var counts = data.counts || {};
    setCaption(captionEl, data.note, cellText(counts.count) + ' correlations');

    var tableRows = rows.map(function (row) {
      return [
        cellText(row.proton_a_ppm),
        cellText(row.proton_b_ppm),
        formatIntensity(row.intensity),
      ];
    });
    var table = buildTable(
      ['δH-a (ppm)', 'δH-b (ppm)', 'Intensity'],
      tableRows
    );
    table.className = 'data-table';
    clearChildren(bodyEl);
    bodyEl.appendChild(table);
  }

  // ------------------------------------------------------------------
  // refreshConstraints / renderConstraints — TBL-03 (D-01: structured
  // 3-subsection view, not a single flat table)
  // ------------------------------------------------------------------
  function refreshConstraints() {
    fetch(CONSTRAINTS_URL)
      .then(function (r) { return r.json(); })
      .then(function (data) { renderConstraints(data); })
      .catch(function (e) { console.warn('constraints fetch failed:', e); });
  }

  function renderConstraints(data) {
    var bodyEl = document.getElementById('table-constraints-body');
    var captionEl = document.getElementById('table-constraints-caption');

    if (!data || data.state !== 'ok' || !data.inventory) {
      showTableWaiting(bodyEl, captionEl, 'Waiting for LSD constraint data...');
      return;
    }

    var inv = data.inventory;
    if (captionEl) {
      captionEl.textContent = 'Iteration ' + cellText(inv.iteration) + ' · '
        + cellText(inv.formula) + ' · ' + cellText(inv.timestamp);
    }

    clearChildren(bodyEl);
    bodyEl.appendChild(buildAppliedConstraintsSection(inv));
    bodyEl.appendChild(buildConstraintSummarySection(inv));
    bodyEl.appendChild(buildDeferredPendingSection(inv));
  }

  function buildTablesSubsection(headingText) {
    var section = document.createElement('div');
    section.className = 'tables-subsection';
    var heading = document.createElement('h3');
    heading.className = 'tables-subheading';
    heading.textContent = headingText;
    section.appendChild(heading);
    return section;
  }

  // "Applied Constraints" — one row per per-atom-index constraint instance
  // (BOND / HMBC / COSY-equiv). The Note column would draw from the matching
  // `applied_from_detection` narrative, but the schema carries that as a flat
  // list with no per-row index back to a specific constraint — so every row
  // gets a genuinely empty Note cell (never a placeholder dash) until the
  // backend schema exposes an explicit mapping.
  function buildAppliedConstraintsSection(inv) {
    var section = buildTablesSubsection('Applied Constraints');

    var rows = [];
    var bondConstraints = inv.bond_constraints || [];
    bondConstraints.forEach(function (indices) {
      rows.push(['BOND', cellText(indices), '']);
    });

    var hmbcBatches = inv.hmbc_batches || [];
    hmbcBatches.forEach(function (batch) {
      var correlations = (batch && batch.correlations) || [];
      correlations.forEach(function (indices) {
        rows.push(['HMBC', cellText(indices), '']);
      });
    });

    var cosyEquivPairs = inv.cosy_equiv_pairs || [];
    cosyEquivPairs.forEach(function (indices) {
      rows.push(['COSY-equiv', cellText(indices), '']);
    });

    var table;
    if (rows.length === 0) {
      table = buildTable(['Type', 'Atom Indices', 'Note'], []);
      var tbody = table.querySelector('tbody');
      var emptyRow = document.createElement('tr');
      var emptyCell = document.createElement('td');
      emptyCell.colSpan = 3;
      emptyCell.textContent = 'No applied constraints recorded';
      emptyRow.appendChild(emptyCell);
      tbody.appendChild(emptyRow);
    } else {
      table = buildTable(['Type', 'Atom Indices', 'Note'], rows);
    }
    table.className = 'data-table';
    section.appendChild(table);
    return section;
  }

  // "Constraint Summary" — fixed row order, count/summary-only fields.
  function buildConstraintSummarySection(inv) {
    var section = buildTablesSubsection('Constraint Summary');

    var deffFexp = inv.deff_fexp || {};
    var rows = [
      ['MULT', cellText(inv.mult_count)],
      ['HSQC', cellText(inv.hsqc_count)],
      ['HMBC total', cellText(inv.hmbc_total)],
      ['ELIM budget', cellText(inv.elim_budget)],
      ['Ring exclusion', formatBool(inv.ring_exclusion_enabled)],
      ['DEFF/FEXP status', cellText(deffFexp.status)],
    ];

    var table = buildTable(['Constraint', 'Value'], rows);
    table.className = 'data-table';
    section.appendChild(table);
    return section;
  }

  // "Deferred / Pending" — reasoning narrative list, plain <ul>/<li>.
  function buildDeferredPendingSection(inv) {
    var section = buildTablesSubsection('Deferred / Pending');

    var pending = inv.pending_from_detection || [];
    var ul = document.createElement('ul');
    if (pending.length === 0) {
      var emptyLi = document.createElement('li');
      emptyLi.textContent = 'Nothing deferred this iteration.';
      ul.appendChild(emptyLi);
    } else {
      pending.forEach(function (item) {
        var li = document.createElement('li');
        li.textContent = item;
        ul.appendChild(li);
      });
    }
    section.appendChild(ul);
    return section;
  }

  // ------------------------------------------------------------------
  // refreshSpectra1D — 1D Spectra tab (Phase 95: SP1-01/SP-02).
  // The PNG endpoint is never-500 (placeholder chart baked into the
  // pixels on failure), so no fetch/catch is needed — the browser's
  // native <img> loading handles the binary payload directly. Cache-bust
  // unconditionally every tick (D-06: no SMILES-diff dedupe needed here).
  // ------------------------------------------------------------------
  function refreshSpectra1D() {
    var t = Date.now();
    var carbonImg = document.getElementById('img-spectrum-carbon');
    if (carbonImg) { carbonImg.src = '/api/spectra/1d/carbon?t=' + t; }
    var protonImg = document.getElementById('img-spectrum-proton');
    if (protonImg) { protonImg.src = '/api/spectra/1d/proton?t=' + t; }
  }

  // ------------------------------------------------------------------
  // initTabs — plain class/display toggling, no fetch triggered (D-01)
  // ------------------------------------------------------------------
  function initTabs() {
    var buttons = document.querySelectorAll('#tab-bar [data-tab]');
    var panels = document.querySelectorAll('[data-panel]');

    function activate(tabName) {
      for (var i = 0; i < panels.length; i++) {
        panels[i].style.display = (panels[i].getAttribute('data-panel') === tabName)
          ? 'block' : 'none';
      }
      for (var j = 0; j < buttons.length; j++) {
        var isActive = buttons[j].getAttribute('data-tab') === tabName;
        buttons[j].classList.toggle('active', isActive);
      }
    }

    for (var k = 0; k < buttons.length; k++) {
      buttons[k].addEventListener('click', function (evt) {
        activate(evt.currentTarget.getAttribute('data-tab'));
      });
    }

    activate('log');  // default tab on load
  }

  // ------------------------------------------------------------------
  // Refresh indicator
  // ------------------------------------------------------------------
  function flashDot() {
    var dot = document.getElementById('refresh-dot');
    if (!dot) { return; }
    dot.classList.add('active');
    setTimeout(function () { dot.classList.remove('active'); }, 500);
  }

  function tick() {
    refreshStatus();
    refreshStructures();
    refreshLog();
    refreshCarbon();
    refreshHsqc();
    refreshHmbc();
    refreshCosy();
    refreshSpectra1D();
    refreshConstraints();
    flashDot();
  }

  // ------------------------------------------------------------------
  // Bootstrap
  // ------------------------------------------------------------------
  initTabs();  // one-time: click-driven, not polled
  tick();  // immediate load
  setInterval(tick, REFRESH_MS);  // D-15: ~3 s polling

}());
