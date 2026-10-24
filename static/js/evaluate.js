// Evaluate (EVAL-01, docs/evaluate.md): run the PRG32 performance protocol on a target, then show the
// statistics, the chart and the downloads that the server makes from the dataset (evaluation.py).
// Like Deploy, the target is looked at first and the slot it replaces is confirmed.
(function () {
  const page = $('#evaluatePage');
  if (!page.length) return;
  const TITLE = page.data('cartridge-title');
  const EVIDENCE = {
    prg32: tr('js.deploy.evidence_physical', 'physical device'),
    prg32qt: tr('js.deploy.evidence_qt', 'emulator (PRG32-QT), not physical-device evidence'),
    qemu: tr('js.deploy.evidence_qemu', 'emulator (QEMU), not physical-device evidence')
  };
  const STATUS = {
    queued: tr('js.deploy.status_queued', 'Waiting to start'),
    checking: tr('js.deploy.status_checking', 'Checking the target'),
    uploading: tr('js.deploy.status_uploading', 'Sending the cartridge'),
    measuring: tr('js.evaluate.status_measuring', 'Measuring'),
    complete: tr('js.evaluate.status_complete', 'Complete'),
    refused: tr('js.deploy.status_refused', 'Refused'),
    failed: tr('js.deploy.status_failed', 'Failed'),
    cancelled: tr('js.deploy.status_cancelled', 'Cancelled')
  };
  const FINAL = ['complete', 'refused', 'failed', 'cancelled'];
  const number = new Intl.NumberFormat(document.documentElement.lang || 'en', { maximumFractionDigits: 1 });
  let targets = [];
  let probe = null;
  let following = null;
  let timer = null;
  let shown = null;            // {ids: [...]} of the results on screen

  function said(item, english) { return item && item.message_key ? Kit.serverMessage(item, english) : english; }
  function target() { return targets.find(item => item.id === $('#evalTarget').val()); }
  function slotChoice() { return $('input[name="evalSlot"]:checked').val(); }
  function show(value) { return value === null || value === undefined ? '–' : number.format(value); }

  // The PRG32 Evaluation project of this account and its compiled cartridges.
  function evaluationProject() {
    return Kit.api('/api/projects').then(data => (data.projects || []).find(item => item.title === TITLE));
  }

  function loadCartridges() {
    return evaluationProject().then(project => {
      if (!project) {
        $('#evalCartridge').html(`<option value="">${Kit.escape(tr('js.evaluate.no_cartridge', 'No evaluation cartridge yet: press Make the evaluation cartridge.'))}</option>`);
        return reset();
      }
      return Kit.api('/api/artifacts?kind=prg32_cartridge&project_id=' + encodeURIComponent(project.id)).then(data => {
        const items = (data.artifacts || []).filter(item => item.metadata && item.metadata.sha256)
          .sort((a, b) => (b.created_at || '').localeCompare(a.created_at || ''));
        $('#evalCartridge').html(items.map(item => `<option value="${Kit.escape(item.id)}">${Kit.escape(item.metadata.architecture)} · ${Kit.escape((item.created_at || '').replace('T', ' ').slice(0, 16))} · SHA-256 ${Kit.escape(item.metadata.sha256.slice(0, 12))}</option>`).join('')
          || `<option value="">${Kit.escape(tr('js.evaluate.no_cartridge', 'No evaluation cartridge yet: press Make the evaluation cartridge.'))}</option>`);
        reset();
      });
    });
  }

  // Make (or update) the project from the protocol's own source, then compile it.
  function make() {
    $('#evalMake').prop('disabled', true);
    Kit.api('/api/evaluation/protocol').then(protocol => evaluationProject().then(project => {
      const game = { source_mode: 'c', source_c: protocol.cartridge.source_text, required_features: protocol.cartridge.required_features };
      return project ? Kit.api('/api/projects/' + encodeURIComponent(project.id), { method: 'PUT', body: { game_json: game, expected_version: project.version } })
        : Kit.api('/api/projects', { method: 'POST', body: { title: protocol.cartridge.title, game_json: game } });
    })).then(project => {
      Kit.toast(tr('js.evaluate.compiling', 'Compiling the evaluation cartridge...'), 'info');
      return Kit.api(`/api/projects/${encodeURIComponent(project.id)}/package`, { method: 'POST', body: {} });
    }).then(() => loadCartridges())
      .catch(err => Kit.toast(err.message, 'danger'))
      .finally(() => $('#evalMake').prop('disabled', false));
  }

  function loadTargets() {
    return Kit.api('/api/deploy/targets').then(list => {
      targets = list;
      $('#evalNoTargets').toggleClass('d-none', list.length > 0);
      $('#evalTarget').html(list.map(item => `<option value="${Kit.escape(item.id)}">${Kit.escape(item.name)} · ${Kit.escape(EVIDENCE[item.kind])}</option>`).join(''));
      reset();
    });
  }

  function reset() {
    probe = null;
    $('#evalProbe').empty();
    $('#evalConfirm').prop('checked', false).prop('disabled', true);
    $('#evalConfirmLabel').text(tr('deploy.confirm_first', 'Look at the target and choose a slot first.'));
    updateButtons();
  }

  function updateButtons() {
    const running = following && !FINAL.includes(following.status);
    $('#evalStart').prop('disabled', !(probe && slotChoice() && $('#evalConfirm').is(':checked') && $('#evalCartridge').val()) || running);
    $('#evalCancel').prop('disabled', !running);
    $('#evalLook').prop('disabled', !target() || running);
    $('#evalCompare').prop('disabled', $('.eval-pick:checked').length < 1);
  }

  function look() {
    const chosen = target();
    $('#evalProbe').html(`<p class="text-muted">${Kit.escape(tr('js.deploy.looking', 'Asking the target who it is...'))}</p>`);
    Kit.api(`/api/deploy/targets/${encodeURIComponent(chosen.id)}/probe`, { method: 'POST', body: { artifact_id: $('#evalCartridge').val() || null } })
      .then(answer => {
        probe = answer;
        const rows = answer.slots.map(slot => {
          const blocked = (slot.problems || []).length > 0;
          const content = slot.fresh ? tr('js.deploy.slot_fresh', 'a fresh copy of the firmware: nothing is replaced')
            : slot.stored ? tr('js.deploy.slot_holds', 'holds "{name}" ({bytes} bytes of code)', { name: slot.name || '?', bytes: slot.code_size })
              : tr('js.deploy.slot_empty', 'empty');
          return `<div class="form-check"><input class="form-check-input" type="radio" name="evalSlot" id="eval-${Kit.escape(slot.slot)}" value="${Kit.escape(slot.slot)}" data-content="${Kit.escape(content)}" ${blocked ? 'disabled' : ''}>
            <label class="form-check-label" for="eval-${Kit.escape(slot.slot)}"><code>${Kit.escape(slot.slot)}</code> ${Kit.escape(content)}</label>
            ${(slot.problems || []).map(item => `<div class="text-danger small">${Kit.escape(said(item, item.error))}</div>`).join('')}</div>`;
        }).join('');
        const problems = (answer.abi_problems || []).map(item => `<li>${Kit.escape(said(item, item.error))}</li>`).join('');
        $('#evalProbe').html(`<p class="small mb-1">${Kit.escape(answer.identity.name)} ${Kit.escape(answer.identity.firmware_version)} (${Kit.escape(answer.identity.host)}) · ${Kit.escape(EVIDENCE[chosen.kind])}</p>
          ${answer.cartridge_problem ? `<div class="alert alert-warning">${Kit.escape(said(answer.cartridge_problem, answer.cartridge_problem.error))}</div>` : ''}
          ${problems ? `<div class="alert alert-danger"><ul class="mb-0">${problems}</ul></div>` : ''}
          <fieldset><legend class="small">${Kit.escape(tr('js.deploy.slots_caption', 'Choose the slot to use. What is in it is replaced.'))}</legend>${rows}</fieldset>`);
        updateButtons();
      })
      .catch(err => { probe = null; $('#evalProbe').html(`<div class="alert alert-danger">${Kit.escape(err.message)}</div>`); updateButtons(); });
  }

  $('#evalProbe').on('change', 'input[name="evalSlot"]', function () {
    $('#evalConfirm').prop('checked', false).prop('disabled', false);
    $('#evalConfirmLabel').text(tr('js.deploy.confirm_replace', 'Replace what is in {slot} ({content}) on {target}', {
      slot: this.value, content: $(this).data('content'), target: target().name
    }));
    updateButtons();
  });
  $('#evalConfirm').on('change', updateButtons);

  function start() {
    const name = slotChoice();
    const slot = probe.slots.find(item => item.slot === name);
    Kit.api('/api/evaluations', { method: 'POST', body: {
      artifact_id: $('#evalCartridge').val(), target: target().id, slot: name, confirm: true,
      repetitions: Number($('#evalRepetitions').val()), warm_up: Number($('#evalWarmUp').val()),
      expect: { fingerprint: probe.fingerprint, slot_content: { slot: slot.slot, stored: slot.stored, name: slot.name, code_size: slot.code_size, mem_size: slot.mem_size } }
    } }).then(follow).catch(err => Kit.toast(err.message, 'danger'));
  }

  function follow(item) {
    following = item;
    $('#evalProgress').attr('aria-valuenow', item.progress).find('.progress-bar').css('width', item.progress + '%')
      .toggleClass('bg-success', item.status === 'complete').toggleClass('bg-danger', ['refused', 'failed'].includes(item.status));
    const error = item.result && item.result.error ? ' · ' + said(item.result, item.result.error) : '';
    $('#evalStatus').text((STATUS[item.status] || item.status) + error);
    $('#evalLog').html(item.log.map(line => `<li>${Kit.escape(said(line, line.text))}</li>`).join(''));
    updateButtons();
    clearTimeout(timer);
    if (!FINAL.includes(item.status)) {
      timer = setTimeout(() => Kit.api('/api/evaluations/' + encodeURIComponent(item.id)).then(follow)
        .catch(err => Kit.toast(err.message, 'danger')), 1000);
    } else {
      reset();
      loadHistory().then(() => { if (item.status === 'complete' || item.status === 'cancelled') results([item.id]); });
    }
  }

  // Results: the server's statistics and chart for one evaluation, or the comparison of several.
  function results(ids) {
    shown = { ids };
    const metric = $('#evalMetric').val();
    const query = 'ids=' + ids.map(encodeURIComponent).join(',') + '&metric=' + encodeURIComponent(metric);
    Kit.api('/api/evaluations/compare.json?' + query).then(answer => {
      const unit = answer.metric.unit;
      const metricName = $('#evalMetric option:selected').text().replace(/\s*\([^)]*\)$/, '');   // without its unit
      $('#evalTableCaption').text(tr('js.evaluate.table_caption', '{metric} in {unit}: over the measured runs; 95% CI is the Student t interval of the mean.', {
        metric: metricName, unit
      }));
      $('#evalTable tbody').html(answer.targets.map(item => item.cases.map(data => `<tr>
        <th scope="row">${Kit.escape(item.target_name)} · ${Kit.escape(data.case)} <span class="badge ${item.physical_device ? 'text-bg-success' : 'text-bg-secondary'}">${Kit.escape(EVIDENCE[item.target_kind])}</span></th>
        <td class="text-end">${data.n}</td><td class="text-end">${show(data.mean)}</td><td class="text-end">${show(data.sd)}</td>
        <td class="text-end">${data.ci95_low === null ? '–' : show(data.ci95_low) + ' – ' + show(data.ci95_high)}</td>
        <td class="text-end">${show(data.median)}</td><td class="text-end">${data.n ? show(data.min) + ' – ' + show(data.max) : tr('js.evaluate.no_data', 'no data')}</td></tr>`).join('')).join(''));
      const base = ids.length === 1 ? `/api/evaluations/${encodeURIComponent(ids[0])}` : '/api/evaluations/compare';
      const files = ids.length === 1 ? { csv: '/dataset.csv', json: '/dataset.json', svg: '/chart.svg', pdf: '/chart.pdf' } : { csv: '.csv', json: '.json', svg: '.svg', pdf: '.pdf' };
      const extra = ids.length === 1 ? '?metric=' + encodeURIComponent(metric) : '?' + query;
      $('#evalChart').attr('src', base + files.svg + extra + '&inline=1')
        .attr('alt', tr('js.evaluate.chart_alt', 'Bar chart of {metric} per case for {targets}; the same numbers are in the table above.', {
          metric: metricName, targets: answer.targets.map(item => item.target_name).join(', ')
        }));
      $('#evalChartCaption').text(tr('js.evaluate.chart_caption', 'Bars: mean; lines: 95% confidence interval; points: every measured run. Emulator times are not PRG32 console times.'));
      $('#evalFigure').prop('hidden', false);
      $('#evalDownloads').html([['csv', tr('js.evaluate.download_csv', 'Raw data (CSV)')], ['json', tr('js.evaluate.download_json', 'Raw data and provenance (JSON)')],
        ['svg', tr('js.evaluate.download_svg', 'Chart (SVG)')], ['pdf', tr('js.evaluate.download_pdf', 'Chart (PDF)')]].map(([kind, label]) =>
        `<a class="btn btn-outline-secondary btn-sm" href="${Kit.escape(base + files[kind] + (kind === 'svg' || kind === 'pdf' ? extra : (ids.length === 1 ? '' : '?' + query)))}" download><i class="bi bi-download" aria-hidden="true"></i> ${Kit.escape(label)}</a>`).join(''));
      const reasons = { protocol: tr('js.evaluate.other_protocol', 'another protocol version'),
        cartridge: tr('js.evaluate.other_cartridge', 'another cartridge (different SHA-256)') };
      $('#evalLeftOut').html(answer.left_out.map(item => `<div class="alert alert-info small mb-1">${Kit.escape(tr('js.evaluate.left_out', '{id} is not on this chart: {reason}.', { id: item.evaluation_id, reason: reasons[item.code] || item.reason }))}</div>`).join(''));
    }).catch(err => Kit.toast(err.message, 'danger'));
  }

  function loadHistory() {
    return Kit.api('/api/evaluations').then(list => {
      $('#evalHistory').html(list.map(item => `<li class="list-group-item small d-flex flex-wrap gap-2 align-items-center">
        <input class="form-check-input eval-pick" type="checkbox" value="${Kit.escape(item.id)}" id="pick-${Kit.escape(item.id)}" ${item.status === 'complete' ? '' : 'disabled'}>
        <label class="form-check-label me-auto" for="pick-${Kit.escape(item.id)}">${Kit.escape(item.target_name)} · ${Kit.escape((item.created_at || '').replace('T', ' ').slice(0, 16))} · ${Kit.escape(tr('js.evaluate.runs', '{measured} measured + {warm} warm-up runs', { measured: item.repetitions, warm: item.warm_up }))} · SHA-256 ${Kit.escape(((item.result.cartridge || {}).sha256 || '').slice(0, 12))}</label>
        <span class="badge ${item.physical_device ? 'text-bg-success' : 'text-bg-secondary'}">${Kit.escape(EVIDENCE[item.target_kind])}</span>
        <span class="badge ${item.status === 'complete' ? 'text-bg-primary' : 'text-bg-light'}">${Kit.escape(STATUS[item.status] || item.status)}</span>
        ${item.status === 'complete' ? `<button class="btn btn-link btn-sm p-0 eval-open" type="button" data-id="${Kit.escape(item.id)}">${Kit.escape(tr('js.evaluate.open', 'Show'))}</button>` : ''}
      </li>`).join('') || `<li class="list-group-item small text-muted">${Kit.escape(tr('js.evaluate.no_history', 'No evaluation yet.'))}</li>`);
      updateButtons();
    });
  }

  $('#evalHistory').on('change', '.eval-pick', updateButtons);
  $('#evalHistory').on('click', '.eval-open', function () { results([$(this).data('id')]); });
  $('#evalCompare').on('click', () => results($('.eval-pick:checked').map(function () { return this.value; }).get()));
  $('#evalMetric').on('change', () => { if (shown) results(shown.ids); });
  $('#evalCartridge, #evalTarget').on('change', reset);
  $('#evalMake').on('click', make);
  $('#evalLook').on('click', look);
  $('#evalStart').on('click', start);
  $('#evalCancel').on('click', () => following && Kit.api(`/api/evaluations/${encodeURIComponent(following.id)}/cancel`, { method: 'POST', body: {} })
    .then(() => $('#evalStatus').text(tr('js.deploy.cancelling', 'Cancelling after this step...'))).catch(err => Kit.toast(err.message, 'danger')));
  Promise.all([loadTargets(), loadCartridges(), loadHistory()]).catch(err => Kit.toast(err.message, 'danger'));
})();
