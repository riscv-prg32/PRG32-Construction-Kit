// Deploy (ADR-0028, docs/deploy.md): choose a compiled cartridge and a target, look at the target,
// confirm the slot it replaces, then follow each step. The server does the work (deploy.py); this
// page only shows it, and never sends anything the student did not confirm.
(function () {
  const page = $('#deployPage');
  if (!page.length) return;
  const isAdmin = page.data('admin') === true;
  const KIND_NAMES = {
    prg32: tr('deploy.kind_prg32', 'PRG32 console'),
    prg32qt: tr('deploy.kind_prg32qt', 'PRG32-QT'),
    qemu: tr('deploy.kind_qemu', 'QEMU (this server)')
  };
  const EVIDENCE = {
    prg32: tr('js.deploy.evidence_physical', 'physical device'),
    prg32qt: tr('js.deploy.evidence_qt', 'emulator (PRG32-QT), not physical-device evidence'),
    qemu: tr('js.deploy.evidence_qemu', 'emulator (QEMU), not physical-device evidence')
  };
  const STATUS = {
    queued: tr('js.deploy.status_queued', 'Waiting to start'),
    checking: tr('js.deploy.status_checking', 'Checking the target'),
    uploading: tr('js.deploy.status_uploading', 'Sending the cartridge'),
    starting: tr('js.deploy.status_starting', 'Starting it'),
    verifying: tr('js.deploy.status_verifying', 'Checking that it runs'),
    launched: tr('js.deploy.status_launched', 'Running'),
    refused: tr('js.deploy.status_refused', 'Refused'),
    failed: tr('js.deploy.status_failed', 'Failed'),
    cancelled: tr('js.deploy.status_cancelled', 'Cancelled')
  };
  const FINAL = ['launched', 'refused', 'failed', 'cancelled'];
  let targets = [];
  let probe = null;          // what the student saw when they looked at the target
  let following = null;      // the deployment being followed
  let timer = null;

  // A server message in the reader's language: {text or error, message_key, params}.
  function said(item, english) {
    return item && item.message_key ? Kit.serverMessage(item, english) : english;
  }

  function cartridgeId() { return $('#deployCartridge').val(); }
  function target() { return targets.find(item => item.id === $('#deployTarget').val()); }
  function slotChoice() { return $('input[name="deploySlot"]:checked').val(); }

  function loadProjects() {
    return Kit.api('/api/projects').then(data => {
      const projects = data.projects || [];
      const wanted = page.data('project') || '';
      $('#deployProject').html(`<option value="">${Kit.escape(tr('js.deploy.choose_project', 'Choose a project'))}</option>` +
        projects.map(item => `<option value="${Kit.escape(item.id)}">${Kit.escape(item.title)}</option>`).join(''));
      if (wanted) $('#deployProject').val(wanted);
      return loadCartridges();
    });
  }

  function loadCartridges() {
    const project = $('#deployProject').val();
    if (!project) {
      $('#deployCartridge').html(`<option value="">${Kit.escape(tr('js.deploy.choose_project_first', 'Choose a project first'))}</option>`);
      return Promise.resolve(reset());
    }
    return Kit.api('/api/artifacts?kind=prg32_cartridge&project_id=' + encodeURIComponent(project)).then(data => {
      const items = (data.artifacts || []).filter(item => item.metadata && item.metadata.sha256)
        .sort((a, b) => (b.created_at || '').localeCompare(a.created_at || ''));
      $('#deployCartridge').html(items.length ? items.map(item => {
        const meta = item.metadata;
        return `<option value="${Kit.escape(item.id)}" data-architecture="${Kit.escape(meta.architecture)}" data-sha256="${Kit.escape(meta.sha256)}">${Kit.escape(item.name)} · ${Kit.escape(meta.architecture)} · ${Kit.escape((item.created_at || '').replace('T', ' ').slice(0, 16))} · ${Kit.escape(meta.sha256.slice(0, 12))}</option>`;
      }).join('') : `<option value="">${Kit.escape(tr('js.deploy.no_cartridges', 'No compiled cartridge yet: open the project and press Compile.'))}</option>`);
      reset();
      loadHistory();
    });
  }

  function loadTargets() {
    return Kit.api('/api/deploy/targets').then(list => {
      targets = list;
      $('#deployNoTargets').toggleClass('d-none', list.length > 0);
      $('#deployTarget').html(list.map(item => `<option value="${Kit.escape(item.id)}">${Kit.escape(item.name)} · ${Kit.escape(KIND_NAMES[item.kind] || item.kind)}</option>`).join(''));
      if (isAdmin) showTargetList();
      reset();
    });
  }

  // Changing the cartridge or the target means looking again: what was seen no longer applies.
  function reset() {
    probe = null;
    $('#deployProbe').empty();
    $('#deployConfirm').prop('checked', false).prop('disabled', true);
    $('#deployConfirmLabel').text(tr('deploy.confirm_first', 'Look at the target and choose a slot first.'));
    updateButtons();
  }

  function updateButtons() {
    const running = following && !FINAL.includes(following.status);
    $('#deployStart').prop('disabled', !(probe && slotChoice() && $('#deployConfirm').is(':checked') && cartridgeId()) || running);
    $('#deployCancel').prop('disabled', !running);
    $('#deployLook').prop('disabled', !target() || running);
  }

  function look() {
    const chosen = target();
    if (!chosen) return;
    $('#deployProbe').html(`<p class="text-muted">${Kit.escape(tr('js.deploy.looking', 'Asking the target who it is...'))}</p>`);
    Kit.api(`/api/deploy/targets/${encodeURIComponent(chosen.id)}/probe`, { method: 'POST', body: { artifact_id: cartridgeId() || null } })
      .then(answer => { probe = answer; showProbe(chosen); })
      .catch(err => { probe = null; $('#deployProbe').html(`<div class="alert alert-danger">${Kit.escape(err.message)}</div>`); updateButtons(); });
  }

  function slotText(slot) {
    if (slot.fresh) return tr('js.deploy.slot_fresh', 'a fresh copy of the firmware: nothing is replaced');
    return slot.stored ? tr('js.deploy.slot_holds', 'holds "{name}" ({bytes} bytes of code)', { name: slot.name || '?', bytes: slot.code_size })
      : tr('js.deploy.slot_empty', 'empty');
  }

  function showProbe(chosen) {
    const identity = probe.identity;
    const problems = (probe.abi_problems || []).map(item => `<li>${Kit.escape(said(item, item.error))}</li>`).join('');
    const cartridgeProblem = probe.cartridge_problem ? `<div class="alert alert-warning">${Kit.escape(said(probe.cartridge_problem, probe.cartridge_problem.error))}</div>` : '';
    const rows = probe.slots.map(slot => {
      const blocked = (slot.problems || []).length > 0;
      const id = 'slot-' + slot.slot;
      return `<tr>
        <td><input class="form-check-input" type="radio" name="deploySlot" id="${Kit.escape(id)}" value="${Kit.escape(slot.slot)}" ${blocked ? 'disabled' : ''}></td>
        <td><label for="${Kit.escape(id)}"><code>${Kit.escape(slot.slot)}</code></label></td>
        <td>${Kit.escape(slotText(slot))}${slot.loaded ? ` <span class="badge text-bg-secondary">${Kit.escape(tr('js.deploy.running_now', 'running now'))}</span>` : ''}
          ${(slot.problems || []).map(item => `<div class="text-danger small">${Kit.escape(said(item, item.error))}</div>`).join('')}</td>
      </tr>`;
    }).join('');
    $('#deployProbe').html(`${cartridgeProblem}
      <dl class="row small mb-2">
        <dt class="col-sm-4">${Kit.escape(tr('js.deploy.firmware', 'Firmware'))}</dt><dd class="col-sm-8">${Kit.escape(identity.name)} ${Kit.escape(identity.firmware_version)} (${Kit.escape(identity.host)})</dd>
        <dt class="col-sm-4">${Kit.escape(tr('js.deploy.abi', 'Cartridge ABI'))}</dt><dd class="col-sm-8">${Kit.escape(String(probe.abi.major))}.${Kit.escape(String(probe.abi.minor))} · <code>0x${probe.abi.hash.toString(16).padStart(8, '0')}</code></dd>
        <dt class="col-sm-4">${Kit.escape(tr('js.deploy.evidence', 'What a run proves'))}</dt><dd class="col-sm-8">${Kit.escape(EVIDENCE[chosen.kind])}</dd>
      </dl>
      ${problems ? `<div class="alert alert-danger"><ul class="mb-0">${problems}</ul></div>` : ''}
      <table class="table table-sm align-middle mb-0">
        <caption class="small">${Kit.escape(tr('js.deploy.slots_caption', 'Choose the slot to use. What is in it is replaced.'))}</caption>
        <thead><tr><th scope="col"><span class="visually-hidden">${Kit.escape(tr('js.deploy.choose', 'Choose'))}</span></th><th scope="col">${Kit.escape(tr('js.deploy.slot', 'Slot'))}</th><th scope="col">${Kit.escape(tr('js.deploy.content', 'Now'))}</th></tr></thead>
        <tbody>${rows}</tbody>
      </table>`);
    updateButtons();
  }

  function slotSeen(name) {
    const slot = probe.slots.find(item => item.slot === name) || {};
    return { slot: slot.slot, stored: slot.stored, name: slot.name, code_size: slot.code_size, mem_size: slot.mem_size };
  }

  $('#deployProbe').on('change', 'input[name="deploySlot"]', function () {
    const slot = probe.slots.find(item => item.slot === this.value);
    $('#deployConfirm').prop('checked', false).prop('disabled', false);
    $('#deployConfirmLabel').text(tr('js.deploy.confirm_replace', 'Replace what is in {slot} ({content}) on {target}', {
      slot: slot.slot, content: slotText(slot), target: target().name
    }));
    updateButtons();
  });
  $('#deployConfirm').on('change', updateButtons);

  function start() {
    const name = slotChoice();
    Kit.api('/api/deployments', { method: 'POST', body: {
      artifact_id: cartridgeId(), target: target().id, slot: name, confirm: true,
      expect: { fingerprint: probe.fingerprint, slot_content: slotSeen(name) }
    } }).then(item => { follow(item); })
      .catch(err => Kit.toast(err.message, 'danger'));
  }

  function follow(item) {
    following = item;
    show(item);
    clearTimeout(timer);
    if (!FINAL.includes(item.status)) {
      timer = setTimeout(() => Kit.api('/api/deployments/' + encodeURIComponent(item.id)).then(follow)
        .catch(err => Kit.toast(err.message, 'danger')), 700);
    } else {
      reset();
      loadHistory();
    }
  }

  function show(item) {
    $('#deployProgress').attr('aria-valuenow', item.progress).find('.progress-bar').css('width', item.progress + '%')
      .toggleClass('bg-success', item.status === 'launched').toggleClass('bg-danger', ['refused', 'failed'].includes(item.status));
    $('#deployStatus').text(STATUS[item.status] || item.status);
    $('#deployLog').html(item.log.map(line => `<li>${Kit.escape(said(line, line.text))}</li>`).join(''));
    const result = item.result || {};
    let html = '';
    if (item.status === 'launched') {
      html = `<div class="alert alert-success">${Kit.escape(tr('js.deploy.launched', 'The cartridge runs on {target}.', { target: item.target_name }))}
        <div class="small">${Kit.escape(tr('js.deploy.proves', 'What this run proves: {evidence}.', { evidence: EVIDENCE[item.target_kind] }))}</div></div>`;
    } else if (FINAL.includes(item.status)) {
      const left = result.left_key ? tr(result.left_key, result.left, result.left_params || {}) : (result.left || '');
      html = `<div class="alert ${item.status === 'cancelled' ? 'alert-secondary' : 'alert-danger'}">
        ${result.error ? `<div>${Kit.escape(said(result, result.error))}</div>` : ''}
        ${left ? `<div class="small mt-1"><strong>${Kit.escape(tr('js.deploy.target_now', 'The target now:'))}</strong> ${Kit.escape(left)}</div>` : ''}</div>`;
    }
    if (item.screenshot) {
      html += `<figure class="figure"><img class="figure-img img-fluid border deploy-screen" src="${Kit.escape(item.screenshot)}" alt="${Kit.escape(tr('js.deploy.screenshot_alt', 'The screen of {target} after the cartridge started', { target: item.target_name }))}">
        <figcaption class="figure-caption">${Kit.escape(tr('js.deploy.screenshot', 'Screenshot from the target'))}</figcaption></figure>`;
    }
    $('#deployResult').html(html);
    updateButtons();
  }

  function cancel() {
    if (!following) return;
    Kit.api(`/api/deployments/${encodeURIComponent(following.id)}/cancel`, { method: 'POST', body: {} })
      .then(item => { $('#deployStatus').text(tr('js.deploy.cancelling', 'Cancelling after this step...')); following = item; })
      .catch(err => Kit.toast(err.message, 'danger'));
  }

  function loadHistory() {
    const project = $('#deployProject').val();
    return Kit.api('/api/deployments' + (project ? '?project_id=' + encodeURIComponent(project) : '')).then(list => {
      $('#deployHistory').html(list.slice(0, 10).map(item => `<li class="list-group-item small d-flex justify-content-between gap-2">
        <span>${Kit.escape(item.target_name)} · <code>${Kit.escape(item.slot)}</code> · ${Kit.escape((item.created_at || '').replace('T', ' ').slice(0, 16))}</span>
        <span class="badge ${item.status === 'launched' ? 'text-bg-success' : FINAL.includes(item.status) ? 'text-bg-danger' : 'text-bg-secondary'}">${Kit.escape(STATUS[item.status] || item.status)}</span>
      </li>`).join('') || `<li class="list-group-item small text-muted">${Kit.escape(tr('js.deploy.no_history', 'Nothing deployed yet.'))}</li>`);
    });
  }

  // Administrators: the consoles and PRG32-QT computers of the class.
  function showTargetList() {
    $('#deployTargetList').html(targets.filter(item => item.kind !== 'qemu').map(item => `<li class="list-group-item d-flex justify-content-between align-items-center">
      <span>${Kit.escape(item.name)} · ${Kit.escape(KIND_NAMES[item.kind])} · <code>${Kit.escape(item.address)}</code></span>
      <button class="btn btn-outline-danger btn-sm remove-target" type="button" data-id="${Kit.escape(item.id)}">${Kit.escape(tr('common.delete', 'Delete'))}</button>
    </li>`).join('') || `<li class="list-group-item small text-muted">${Kit.escape(tr('js.deploy.no_targets_yet', 'No console or PRG32-QT registered yet.'))}</li>`);
  }

  $('#deployTargetForm').on('submit', function (event) {
    event.preventDefault();
    const form = new FormData(this);
    Kit.api('/api/admin/deploy_targets', { method: 'POST', body: { name: form.get('name'), kind: form.get('kind'), address: form.get('address') } })
      .then(() => { this.reset(); Kit.toast(tr('js.deploy.target_added', 'Target added'), 'success'); return loadTargets(); })
      .catch(err => Kit.toast(err.message, 'danger'));
  });
  $('#deployTargetList').on('click', '.remove-target', function () {
    Kit.api('/api/admin/deploy_targets/' + encodeURIComponent($(this).data('id')), { method: 'DELETE' })
      .then(loadTargets).catch(err => Kit.toast(err.message, 'danger'));
  });

  $('#deployProject').on('change', loadCartridges);
  $('#deployCartridge, #deployTarget').on('change', reset);
  $('#deployLook').on('click', look);
  $('#deployStart').on('click', start);
  $('#deployCancel').on('click', cancel);
  Promise.all([loadTargets(), loadProjects()]).then(loadHistory).catch(err => Kit.toast(err.message, 'danger'));
})();
