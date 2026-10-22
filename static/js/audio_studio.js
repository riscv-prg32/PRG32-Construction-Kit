// AudioStudio (docs/audio_studio.md): a project's instruments, sound effects, soundtracks and
// samples, heard through the PRG32 sound engine (prg32_audio.js, ADR-0021).
//
// The page edits one document (format in prg32_construction_kit/audio_studio.py). Every change
// is saved a moment later with the version this window loaded, so a save never overwrites
// sound changed in another window: the student chooses what to keep.
(function () {
  'use strict';

  const projectId = encodeURIComponent($('#projectId').val());
  const canEdit = $('#canEdit').val() === 'yes';
  const api = '/api/projects/' + projectId + '/audio';
  const SOUNDS = ['triangle', 'saw', 'pulse', 'noise', 'sample'];
  const NOTE_NAMES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B'];
  const MAX_EFFECTS = 24;
  const MAX_TRACKS = 16;

  let doc = null;          // the document being edited
  let version = 0;         // the saved version this window started from
  let saveTimer = null;
  let saving = null;
  let changedWhileSaving = false;
  const selected = { voice: 0, effect: 0, track: 0 };
  const muted = new Set();  // soundtrack rows (voices) silenced in the preview
  const engine = new window.PRG32AudioEngine();
  let previewKey = null;    // which document the engine has loaded

  function status(text) { $('#audioStatus').text(text); }

  // Without an account the page does not know the game's title: it is in this browser (ADR-0023).
  Kit.api('/api/projects/' + projectId).then(project => $('#projectTitle').text(project.title)).catch(() => {});

  // ---- notes ---------------------------------------------------------------------------
  // MIDI note 60 is middle C, written C4.
  function noteName(note) { return NOTE_NAMES[note % 12] + (Math.floor(note / 12) - 1); }
  function parseNote(text) {
    const value = String(text).trim();
    if (value === '' || value === '-' || value === '.') return { ok: true, value: null };
    if (value.toLowerCase() === 'off') return { ok: true, value: 'off' };
    if (/^\d{1,3}$/.test(value)) {
      const number = Number(value);
      return number <= 127 ? { ok: true, value: number } : { ok: false };
    }
    const match = /^([A-Ga-g])(#|b)?(-1|\d)$/.exec(value);
    if (!match) return { ok: false };
    let index = NOTE_NAMES.indexOf(match[1].toUpperCase());
    if (match[2] === '#') index += 1;
    if (match[2] === 'b') index -= 1;
    const note = (Number(match[3]) + 1) * 12 + index;
    return note >= 0 && note <= 127 ? { ok: true, value: note } : { ok: false };
  }
  function cellText(cell) { return cell === null ? '' : cell === 'off' ? 'off' : noteName(cell); }

  // ---- the sound engine ------------------------------------------------------------------
  // The preview plays the document as it is on screen, saved or not: the server packs it into
  // the PRG32 audio block (the same bytes a cartridge gets) and the engine loads that block.
  function preview() {
    const key = JSON.stringify([doc, Array.from(muted).sort()]);
    if (key === previewKey) return Promise.resolve(engine);
    return Kit.api(api + '/preview', { method: 'POST', body: { document: doc, muted: Array.from(muted) } })
      .then(block => engine.start(block))
      .then(() => { previewKey = key; return engine; });
  }
  function listen(play) {
    engine.resume();   // inside the click: browsers allow sound only after one
    return preview().then(play).catch(err => status('Cannot play: ' + err.message));
  }
  function stopSound() {
    engine.stop();
    $('.track-step.playing').removeClass('playing');
    status('Sound stopped.');
  }

  // ---- saving ----------------------------------------------------------------------------
  function changed() {
    if (!canEdit) return;
    previewKey = null;
    showIds();
    status('Changes not saved yet…');
    clearTimeout(saveTimer);
    saveTimer = setTimeout(save, 1200);
  }

  function save(overVersion) {
    clearTimeout(saveTimer);
    saveTimer = null;
    if (!canEdit) return Promise.resolve();
    if (saving) { changedWhileSaving = true; return saving; }
    status('Saving…');
    const expected = overVersion === undefined ? version : overVersion;
    saving = Kit.api(api, { method: 'PUT', body: { document: doc, expected_version: expected } })
      .then(answer => {
        version = answer.version;
        showMissing(answer.missing_samples);
        status('Saved (version ' + version + ').');
        // The IDE refreshes the sound names on its blocks and the game's sound.
        $(document).trigger('prg32:audio-saved', [answer]);
      })
      .catch(err => {
        if (err.code === 'audio_version_conflict') {
          status('Not saved: this sound was changed in another window.');
          Kit.versionConflict(err, {
            copy: () => { download(); return Promise.resolve(); },
            reload: () => load(),
            overwrite: currentVersion => { saving = null; return save(currentVersion); },
          });
        } else {
          status('Not saved: ' + err.message);
          Kit.toast(err.message, 'danger');
        }
      })
      .finally(() => {
        saving = null;
        if (changedWhileSaving) { changedWhileSaving = false; changed(); }
      });
    return saving;
  }

  function load() {
    return Kit.api(api).then(answer => {
      doc = answer.document;
      version = answer.version;
      previewKey = null;
      showMissing(answer.missing_samples);
      renderAll();
      status(version ? 'Loaded version ' + version + '.' : 'A new AudioStudio sound: change anything to save it.');
    }).catch(err => status('Could not load the sound: ' + err.message));
  }

  function download() { Kit.download(api + '/export'); }

  function showMissing(names) {
    const box = $('#missingSamples');
    if (!names || !names.length) { box.addClass('d-none').text(''); return; }
    box.removeClass('d-none').text('These samples have no saved sound, so the project cannot play or build: '
      + names.join(', ') + '. Add the WAV file again on the Samples tab.');
  }

  // ---- forms ---------------------------------------------------------------------------
  let fieldCount = 0;
  function field(label, input, help) {
    fieldCount += 1;
    const id = 'audioField' + fieldCount;
    input.attr('id', id).prop('disabled', !canEdit);
    const group = $('<div class="mb-2"></div>').append($('<label class="form-label small mb-0"></label>').attr('for', id).text(label), input);
    if (help) group.append($('<div class="form-text"></div>').text(help));
    return group;
  }
  function numberInput(value, low, high, onChange) {
    const input = $('<input class="form-control form-control-sm" type="number">').attr({ min: low, max: high, step: 1 }).val(value);
    input.on('change', () => {
      const number = Math.max(low, Math.min(high, Math.round(Number(input.val()) || 0)));
      input.val(number);
      onChange(number);
    });
    return input;
  }
  function rangeInput(value, low, high, onChange) {
    const wrap = $('<div class="d-flex align-items-center gap-2"></div>');
    const range = $('<input class="form-range" type="range">').attr({ min: low, max: high, step: 1 }).val(value);
    const shown = $('<output class="small text-muted"></output>').text(value);
    range.on('input', () => { shown.text(range.val()); });
    range.on('change', () => { onChange(Number(range.val())); });
    wrap.append(range, shown);
    wrap.attr = function (name, value2) { range.attr(name, value2); return wrap; };  // field() labels the slider
    wrap.prop = function (name, value2) { range.prop(name, value2); return wrap; };
    return wrap;
  }
  function textInput(value, onChange) {
    const input = $('<input class="form-control form-control-sm" maxlength="32">').val(value);
    input.on('change', () => onChange(input.val().trim()));
    return input;
  }
  function nameOk(name, others) {
    if (!/^[A-Za-z0-9][A-Za-z0-9 _.\-]{0,31}$/.test(name)) { Kit.toast('A name has 1 to 32 letters, digits, spaces, ".", "_" or "-".', 'warning'); return false; }
    if (others.includes(name)) { Kit.toast('Another one is already called ' + name + '.', 'warning'); return false; }
    return true;
  }

  // ADSR times from the PRG32 audio contract: 1 + v*v*2000/65025 ms (0 = at once).
  function stageMs(value) { return value ? 1 + Math.floor(value * value * 2000 / 65025) : 0; }
  function envelope(item) {
    const hold = 400;
    const a = stageMs(item.attack), d = stageMs(item.decay), r = stageMs(item.release);
    const total = Math.max(1, a + d + hold + r);
    const x = ms => (ms / total * 300).toFixed(1);
    const top = 10, bottom = 90, level = bottom - (bottom - top) * item.sustain / 255;
    const points = [[0, bottom], [a, top], [a + d, level], [a + d + hold, level], [a + d + hold + r, bottom]];
    const svg = `<svg viewBox="0 0 300 100" class="adsr-envelope w-100" role="img" aria-label="Envelope: attack ${a} ms, decay ${d} ms, sustain ${item.sustain} of 255, release ${r} ms">
      <polyline fill="none" stroke="currentColor" stroke-width="2" points="${points.map(p => x(p[0]) + ',' + p[1].toFixed(1)).join(' ')}"></polyline>
      <text x="4" y="98" font-size="9">A ${a} ms · D ${d} ms · S ${item.sustain} · R ${r} ms</text></svg>`;
    return $(svg);
  }

  // The settings every instrument has, for a voice or a sound effect.
  function instrumentForm(item, onTry) {
    const box = $('<div class="row g-3"></div>');
    const left = $('<div class="col-md-6"></div>');
    const right = $('<div class="col-md-6"></div>');
    const sound = $('<select class="form-select form-select-sm"></select>');
    SOUNDS.forEach(name => sound.append($('<option></option>').val(name).text(name)));
    sound.val(item.sound);
    const sample = $('<select class="form-select form-select-sm"></select>');
    doc.samples.forEach(entry => sample.append($('<option></option>').val(entry.name).text(entry.name)));
    sample.val(item.sample || '');
    const sampleField = field('Sample', sample, doc.samples.length ? '' : 'Add a sample on the Samples tab first.');
    const synthFields = $('<div></div>').append(
      field('Pulse width (pulse only)', rangeInput(item.pulse_width, 0, 15, v => { item.pulse_width = v; changed(); })),
      field('Filter cutoff', rangeInput(item.cutoff, 0, 15, v => { item.cutoff = v; changed(); }), '15 is bright, 0 is dull'),
      field('Resonance', rangeInput(item.resonance, 0, 3, v => { item.resonance = v; changed(); })));
    function showSound() {
      sampleField.toggleClass('d-none', item.sound !== 'sample');
      synthFields.toggleClass('d-none', item.sound === 'sample');
    }
    sound.on('change', () => {
      item.sound = sound.val();
      if (item.sound === 'sample') {
        if (!doc.samples.length) { Kit.toast('Add a sample on the Samples tab first.', 'warning'); item.sound = 'triangle'; sound.val('triangle'); }
        else item.sample = item.sample || doc.samples[0].name;
        sample.val(item.sample || '');
      } else delete item.sample;
      showSound();
      changed();
    });
    sample.on('change', () => { item.sample = sample.val(); changed(); });
    left.append(field('Sound', sound), sampleField, synthFields,
      field('Volume', rangeInput(item.volume, 0, 255, v => { item.volume = v; changed(); })),
      field('Pan (−64 left … 63 right)', rangeInput(item.pan, -64, 63, v => { item.pan = v; changed(); })));
    const picture = $('<div class="mb-2"></div>').append(envelope(item));
    const redraw = () => picture.empty().append(envelope(item));
    right.append($('<div class="small fw-semibold">Envelope (ADSR)</div>'), picture);
    ['attack', 'decay', 'sustain', 'release'].forEach(key => {
      right.append(field(key[0].toUpperCase() + key.slice(1), rangeInput(item[key], 0, 255, v => { item[key] = v; redraw(); changed(); })));
    });
    right.append($('<button type="button" class="btn btn-primary btn-sm"><i class="bi bi-play-fill"></i> Try it</button>').on('click', onTry));
    showSound();
    return box.append(left, right);
  }

  function listItem(text, active, onClick, extra) {
    const item = $('<button type="button" class="list-group-item list-group-item-action d-flex justify-content-between align-items-center"></button>')
      .toggleClass('active', active).attr('aria-current', active ? 'true' : null).text(text).on('click', onClick);
    if (extra) item.append(extra);
    return item;
  }

  // ---- voices --------------------------------------------------------------------------
  function renderVoices() {
    const list = $('#voiceList').empty();
    doc.voices.forEach((voice, index) => {
      list.append(listItem(index + ': ' + voice.name, index === selected.voice, () => { selected.voice = index; renderVoices(); },
        $('<span class="badge text-bg-secondary"></span>').text(voice.sound)));
    });
    const voice = doc.voices[selected.voice];
    const editor = $('#voiceEditor').empty();
    editor.append($('<h2 class="h5"></h2>').text('Voice ' + selected.voice + ' — instrument ' + selected.voice));
    editor.append(field('Name', textInput(voice.name, name => {
      if (nameOk(name, doc.voices.filter(v => v !== voice).map(v => v.name))) { voice.name = name; renderVoices(); changed(); }
    })));
    editor.append(instrumentForm(voice, () => listen(e => e.note(selected.voice, selected.voice, 60, 255, 500))));
  }

  // ---- sound effects ---------------------------------------------------------------------
  function freeName(base, taken) {
    for (let n = 1; ; n += 1) { const name = base + ' ' + n; if (!taken.includes(name)) return name; }
  }
  function renderEffects() {
    const list = $('#effectList').empty();
    doc.effects.forEach((effect, index) => {
      list.append(listItem(effect.name, index === selected.effect, () => { selected.effect = index; renderEffects(); },
        $('<span class="badge text-bg-secondary"></span>').text('instrument ' + (8 + index))));
    });
    $('#deleteEffect').prop('disabled', !canEdit || !doc.effects.length);
    $('#addEffect').prop('disabled', !canEdit || doc.effects.length >= MAX_EFFECTS);
    const editor = $('#effectEditor').empty();
    const effect = doc.effects[selected.effect];
    if (!effect) { editor.append('<p class="text-muted">No sound effects yet.</p>'); return; }
    const index = selected.effect;
    editor.append($('<h2 class="h5"></h2>').text(effect.name + ' — instrument ' + (8 + index)));
    const row = $('<div class="row g-2"></div>');
    row.append($('<div class="col-sm-4"></div>').append(field('Name', textInput(effect.name, name => {
      if (nameOk(name, doc.effects.filter(e => e !== effect).map(e => e.name))) {
        effect.name = name; effect.instrument.name = name; renderEffects(); changed();
      }
    }), 'Blocks use this name')));
    row.append($('<div class="col-sm-2"></div>').append(field('Note', numberInput(effect.note, 0, 127, v => { effect.note = v; changed(); }), noteName(effect.note))));
    row.append($('<div class="col-sm-2"></div>').append(field('Length (ms)', numberInput(effect.duration_ms, 1, 10000, v => { effect.duration_ms = v; changed(); }))));
    row.append($('<div class="col-sm-2"></div>').append(field('Volume', numberInput(effect.volume, 0, 255, v => { effect.volume = v; changed(); }))));
    row.append($('<div class="col-sm-2"></div>').append(field('Voice', numberInput(effect.voice, 0, 7, v => { effect.voice = v; changed(); }), 'stops what that voice plays')));
    editor.append(row, instrumentForm(effect.instrument,
      () => listen(e => e.note(effect.voice, 8 + index, effect.note, effect.volume, effect.duration_ms))));
  }
  $('#addEffect').on('click', () => {
    const name = freeName('Effect', doc.effects.map(e => e.name));
    doc.effects.push({ name, instrument: { name, sound: 'pulse', pulse_width: 4, cutoff: 15, resonance: 0, volume: 220, pan: 0,
      attack: 0, decay: 60, sustain: 0, release: 40 }, note: 72, duration_ms: 200, volume: 255, voice: 7 });
    selected.effect = doc.effects.length - 1;
    renderEffects();
    changed();
  });
  $('#deleteEffect').on('click', () => {
    const effect = doc.effects[selected.effect];
    if (!effect || !window.confirm('Delete the sound effect ' + effect.name + '? Blocks that play it will warn you.')) return;
    doc.effects.splice(selected.effect, 1);
    selected.effect = Math.max(0, selected.effect - 1);
    renderEffects();
    changed();
  });

  // ---- soundtracks ---------------------------------------------------------------------
  function emptyRows(steps) { return Array.from({ length: 8 }, () => Array.from({ length: steps }, () => null)); }
  function renderTracks() {
    const list = $('#trackList').empty();
    doc.soundtracks.forEach((track, index) => {
      list.append(listItem(track.name, index === selected.track, () => { selected.track = index; renderTracks(); },
        $('<span class="badge text-bg-secondary"></span>').text('track ' + index)));
    });
    $('#deleteTrack').prop('disabled', !canEdit || !doc.soundtracks.length);
    $('#addTrack').prop('disabled', !canEdit || doc.soundtracks.length >= MAX_TRACKS);
    const editor = $('#trackEditor').empty();
    const track = doc.soundtracks[selected.track];
    if (!track) { editor.append('<p class="text-muted">No soundtracks yet.</p>'); return; }
    const index = selected.track;
    editor.append($('<h2 class="h5"></h2>').text(track.name + ' — track ' + index));
    const row = $('<div class="row g-2 align-items-end"></div>');
    row.append($('<div class="col-sm-4"></div>').append(field('Name', textInput(track.name, name => {
      if (nameOk(name, doc.soundtracks.filter(t => t !== track).map(t => t.name))) { track.name = name; renderTracks(); changed(); }
    }), 'Blocks use this name')));
    row.append($('<div class="col-sm-2"></div>').append(field('Tempo (bpm)', numberInput(track.tempo, 30, 255, v => { track.tempo = v; changed(); }))));
    row.append($('<div class="col-sm-2"></div>').append(field('Steps', numberInput(track.steps, 1, 128, v => {
      track.rows = track.rows.map(cells => cells.slice(0, v).concat(Array.from({ length: Math.max(0, v - cells.length) }, () => null)));
      track.steps = v;
      renderTracks();
      changed();
    }))));
    const loop = $('<input class="form-check-input" type="checkbox">').prop('checked', track.loop).prop('disabled', !canEdit)
      .attr('id', 'trackLoop').on('change', () => { track.loop = loop.prop('checked'); changed(); });
    row.append($('<div class="col-sm-2 mb-2"></div>').append($('<div class="form-check"></div>').append(loop,
      $('<label class="form-check-label" for="trackLoop">Loop</label>'))));
    row.append($('<div class="col-sm-2 mb-2"></div>').append($('<button type="button" class="btn btn-primary btn-sm w-100"><i class="bi bi-play-fill"></i> Play</button>')
      .on('click', () => listen(e => { e.playTrack(index); status('Playing ' + track.name + '. Stop sound (or Escape) silences it.'); }))));
    editor.append(row, trackGrid(track));
  }

  function trackGrid(track) {
    const wrap = $('<div class="table-responsive track-grid"></div>');
    const table = $('<table class="table table-sm table-bordered align-middle mb-0"></table>')
      .attr('aria-label', 'Steps of ' + track.name + ': one row per voice');
    const head = $('<tr><th scope="col">Voice</th><th scope="col">Solo</th><th scope="col">Mute</th></tr>');
    for (let step = 0; step < track.steps; step += 1) head.append($('<th scope="col" class="text-center small"></th>').text(step + 1));
    table.append($('<thead></thead>').append(head));
    const body = $('<tbody></tbody>');
    track.rows.forEach((cells, voice) => {
      const tr = $('<tr></tr>').append($('<th scope="row" class="small text-nowrap"></th>').text(voice + ' ' + doc.voices[voice].name));
      const solo = $('<input class="form-check-input" type="checkbox">').attr('aria-label', 'Solo voice ' + voice)
        .prop('checked', muted.size === 7 && !muted.has(voice)).on('change', () => {
          muted.clear();
          if (solo.prop('checked')) for (let other = 0; other < 8; other += 1) if (other !== voice) muted.add(other);
          previewKey = null;
          renderTracks();
        });
      const mute = $('<input class="form-check-input" type="checkbox">').attr('aria-label', 'Mute voice ' + voice)
        .prop('checked', muted.has(voice)).on('change', () => {
          if (mute.prop('checked')) muted.add(voice); else muted.delete(voice);
          previewKey = null;
          renderTracks();
        });
      tr.append($('<td class="text-center"></td>').append(solo), $('<td class="text-center"></td>').append(mute));
      cells.forEach((cell, step) => {
        const input = $('<input class="form-control form-control-sm track-step text-center" maxlength="4" autocomplete="off">')
          .val(cellText(cell)).attr({ 'aria-label': 'Voice ' + voice + ', step ' + (step + 1), 'data-voice': voice, 'data-step': step })
          .prop('readonly', !canEdit);
        input.on('change', () => {
          const parsed = parseNote(input.val());
          input.toggleClass('is-invalid', !parsed.ok);
          if (!parsed.ok) { status('Step ' + (step + 1) + ' of voice ' + voice + ': write a note like C4 or 60, "off", or nothing.'); return; }
          cells[step] = parsed.value;
          input.val(cellText(parsed.value));
          changed();
        });
        tr.append($('<td class="p-0"></td>').append(input));
      });
      body.append(tr);
    });
    table.append(body);
    return wrap.append(table);
  }

  // Arrow keys move around the grid like a spreadsheet; Enter moves down.
  $(document).on('keydown', '.track-step', function (event) {
    const voice = Number($(this).data('voice'));
    const step = Number($(this).data('step'));
    const moves = { ArrowUp: [-1, 0], ArrowDown: [1, 0], Enter: [1, 0], ArrowLeft: [0, -1], ArrowRight: [0, 1] };
    const move = moves[event.key];
    if (!move) return;
    if ((event.key === 'ArrowLeft' || event.key === 'ArrowRight') && this.value && this.selectionStart !== this.selectionEnd) return;
    const target = $(`.track-step[data-voice="${voice + move[0]}"][data-step="${step + move[1]}"]`);
    if (!target.length) return;
    event.preventDefault();
    $(this).trigger('change');
    target.trigger('focus').trigger('select');
  });
  $('#addTrack').on('click', () => {
    doc.soundtracks.push({ name: freeName('Song', doc.soundtracks.map(t => t.name)), tempo: 120, steps: 16, loop: false, rows: emptyRows(16) });
    selected.track = doc.soundtracks.length - 1;
    renderTracks();
    changed();
  });
  $('#deleteTrack').on('click', () => {
    const track = doc.soundtracks[selected.track];
    if (!track || !window.confirm('Delete the soundtrack ' + track.name + '? Blocks that play it will warn you.')) return;
    doc.soundtracks.splice(selected.track, 1);
    selected.track = Math.max(0, selected.track - 1);
    renderTracks();
    changed();
  });

  // ---- samples ---------------------------------------------------------------------------
  function renderSamples() {
    const box = $('#sampleEditor').empty();
    if (!doc.samples.length) { box.append('<p class="text-muted">No samples yet.</p>'); return; }
    const table = $('<table class="table table-sm align-middle"><thead><tr><th scope="col">Name</th><th scope="col">Base note</th><th scope="col">Loop</th><th scope="col">Loop start</th><th scope="col">Loop end</th><th scope="col"><span class="visually-hidden">Actions</span></th></tr></thead></table>');
    const body = $('<tbody></tbody>');
    doc.samples.forEach((sample, index) => {
      const used = doc.voices.concat(doc.effects.map(e => e.instrument)).some(item => item.sound === 'sample' && item.sample === sample.name);
      const loop = $('<input class="form-check-input" type="checkbox">').prop('checked', sample.loop).prop('disabled', !canEdit)
        .attr('aria-label', 'Loop ' + sample.name).on('change', () => { sample.loop = loop.prop('checked'); changed(); });
      const remove = $('<button type="button" class="btn btn-outline-danger btn-sm"><i class="bi bi-trash"></i><span class="visually-hidden">Delete</span></button>')
        .attr('aria-label', 'Delete ' + sample.name).prop('disabled', !canEdit || used)
        .attr('title', used ? 'An instrument plays this sample' : 'Delete').on('click', () => {
          doc.samples.splice(index, 1);
          renderAll();
          changed();
        });
      body.append($('<tr></tr>').append(
        $('<th scope="row"></th>').text(sample.name),
        $('<td></td>').append(numberInput(sample.base_note, 0, 127, v => { sample.base_note = v; changed(); }).attr('aria-label', 'Base note of ' + sample.name).prop('disabled', !canEdit)),
        $('<td></td>').append(loop),
        $('<td></td>').append(numberInput(sample.loop_start, 0, 65535, v => { sample.loop_start = v; changed(); }).attr('aria-label', 'Loop start of ' + sample.name).prop('disabled', !canEdit)),
        $('<td></td>').append(numberInput(sample.loop_end, 0, 65535, v => { sample.loop_end = v; changed(); }).attr('aria-label', 'Loop end of ' + sample.name).prop('disabled', !canEdit)),
        $('<td></td>').append(remove)));
    });
    box.append(table.append(body));
  }
  $('#sampleForm').on('submit', event => {
    event.preventDefault();
    const file = $('#sampleFile')[0].files[0];
    if (!file) { Kit.toast('Choose a WAV file.', 'warning'); return; }
    const name = ($('#sampleName').val() || file.name.replace(/\.[^.]*$/, '')).trim().slice(0, 32);
    if (!nameOk(name, doc.samples.map(s => s.name))) return;
    const form = new FormData();
    form.append('file', file);
    form.append('name', name);
    status('Adding ' + name + '…');
    Kit.api(api + '/samples', { method: 'POST', body: form }).then(sample => {
      doc.samples.push({ name: sample.name, artifact_id: sample.artifact_id, base_note: 60, loop: false, loop_start: 0, loop_end: 0 });
      $('#sampleForm')[0].reset();
      renderAll();
      changed();
      status('Added ' + sample.name + ' (' + sample.seconds.toFixed(2) + ' s).');
    }).catch(err => { status('Sample not added: ' + err.message); Kit.toast(err.message, 'danger'); });
  });

  // ---- the numbers the code uses ---------------------------------------------------------
  function showIds() {
    const lines = ['/* Sound effects: prg32_audio_note(voice, instrument, note, volume, ms) */'];
    doc.effects.forEach((effect, index) => {
      lines.push(`/* ${effect.name} */  prg32_audio_note(${effect.voice}, ${8 + index}, ${effect.note}, ${effect.volume}, ${effect.duration_ms});`);
    });
    if (!doc.effects.length) lines.push('/* (none yet) */');
    lines.push('', '/* Soundtracks */');
    doc.soundtracks.forEach((track, index) => lines.push(`/* ${track.name} */  prg32_audio_play_track(${index});`));
    if (!doc.soundtracks.length) lines.push('/* (none yet) */');
    lines.push('prg32_audio_stop_track();   /* stop the soundtrack */', 'prg32_audio_stop_all();     /* silence every voice */',
      '', '/* In RISC-V assembly the same numbers go in a0..a4 before "call prg32_audio_note". */');
    $('#audioIds').text(lines.join('\n'));
  }

  function renderAll() {
    selected.effect = Math.min(selected.effect, Math.max(0, doc.effects.length - 1));
    selected.track = Math.min(selected.track, Math.max(0, doc.soundtracks.length - 1));
    renderVoices();
    renderEffects();
    renderTracks();
    renderSamples();
    showIds();
    $('.edit-only').toggleClass('d-none', !canEdit);
  }

  // ---- page actions ------------------------------------------------------------------------
  $('#stopSound').on('click', stopSound);
  $(document).on('keydown', event => { if (event.key === 'Escape') stopSound(); });
  $('#saveAudio').on('click', () => save());
  $('#exportAudio').on('click', () => {
    if (saveTimer) Kit.toast('Exporting the last saved version: saving your newest changes first.', 'info');
    Promise.resolve(saveTimer ? save() : null).then(download);
  });
  $('#importAudio').on('change', function () {
    const file = this.files[0];
    this.value = '';
    if (!file) return;
    file.text().then(text => Kit.api(api + '/import', { method: 'POST', body: { export: JSON.parse(text), expected_version: version } }))
      .then(answer => {
        doc = answer.document;
        version = answer.version;
        previewKey = null;
        showMissing(answer.missing_samples);
        renderAll();
        status('Imported and saved (version ' + version + ').');
      })
      .catch(err => {
        if (err.code === 'audio_version_conflict') status('Not imported: this sound was changed in another window. Load it again first.');
        else status('Not imported: ' + (err instanceof SyntaxError ? 'that file is not an AudioStudio export' : err.message));
      });
  });
  window.addEventListener('beforeunload', event => {
    if (saveTimer || saving) { save(); event.preventDefault(); event.returnValue = ''; }
  });

  // For the browser tests and curious teachers in the console: the engine and the document.
  window.PRG32AudioStudio = { engine, document: () => doc, version: () => version };

  load();
})();
