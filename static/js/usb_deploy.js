// Direct USB deployment of one validated PRG32 cartridge (ADR-0020).
// The resident firmware receives the cartridge, displays transfer progress,
// verifies the slot, and launches it without resetting prototype1.
// Contract: PRG32 docs/software/web_usb_deployment.md.
import {
  ProtocolSession, SLOT_NAMES, SLOT_SIZE, cartridgeInfo, cartridgeProblems, choosePort, describeSerialError
} from './prg32_usb_protocol.js';

const $start = $('#usbDeployStart');
const $performance = $('#usbPerformanceGet');
const $confirm = $('#usbDeployConfirm');
const $slot = $('#usbDeploySlot');
const $command = $('#usbDeployCommand');
const $status = $('#usbDeployStatus');
const $log = $('#usbDeployLog');
const $result = $('#usbPerformanceResult');
const $progress = $('#usbDeployProgress');
let busy = false;

function selectedCartridge() {
  const option = document.querySelector('#deployCartridge option:checked');
  return option && option.value ? { id: option.value, architecture: option.dataset.architecture || '', sha256: option.dataset.sha256 || '' } : null;
}

function webSerialAvailable() {
  return Boolean(window.isSecureContext && navigator.serial);
}

function ready() {
  const cartridge = selectedCartridge();
  const supported = webSerialAvailable();
  $('#usbDeployUnsupported').toggleClass('d-none', supported);
  // No slot is chosen for the student: they pick the one whose game may be replaced.
  const slotChosen = SLOT_NAMES.includes($slot.val());
  $start.prop('disabled', busy || !supported || !slotChosen || !$confirm.is(':checked') || !cartridge || cartridge.architecture !== 'esp32c6');
  $performance.prop('disabled', busy || !supported);
}

function appendLog(text) {
  $log.removeClass('d-none').text(($log.text() + String(text) + '\n').slice(-12000));
}

function setProgress(percent) {
  const value = Math.max(0, Math.min(100, Math.round(percent)));
  $progress.removeClass('d-none').attr('aria-valuenow', value).find('.progress-bar').css('width', value + '%');
}

// Web Serial gives the same error names for "another program has the port" (when
// opening) and "the cable was pulled" (once it is open), so the advice depends on
// how far the deploy got. phase: 'opening' (choosing and opening the port),
// 'open' (talking to the PRG32, nothing sent to a slot yet) or 'sending' (the
// upload has begun, so the PRG32 has started erasing the slot).
function lostConnection(error) {
  if (!error) return false;
  if (error.name === 'NetworkError' || error.name === 'InvalidStateError') return true;
  return error.message === 'The PRG32 USB connection closed unexpectedly.';
}

function showError(error, phase = 'opening', slot = '') {
  let message;
  if (error && error.name === 'NotFoundError') {
    message = tr('js.deploy.usb_cancelled', 'No USB device was selected; nothing was written.');
  } else if (phase === 'opening' && lostConnection(error)) {
    message = tr('js.deploy.usb_busy', 'The USB port is busy. Close serial monitors and other programs that use the PRG32, then try again.');
  } else if (phase === 'sending' && lostConnection(error)) {
    message = tr('js.deploy.usb_disconnected_sending', 'The PRG32 was disconnected during the transfer. {slot} may now be empty or hold half a cartridge, which never starts. Plug the PRG32 in again and deploy again.', { slot });
  } else if (lostConnection(error)) {
    message = tr('js.deploy.usb_disconnected', 'The PRG32 was disconnected. Nothing was written. Plug it in again and try again.');
  } else {
    message = describeSerialError(error);
  }
  $status.html('<span class="text-danger"></span>').find('span').text(message);
  appendLog(message);
}

function requestHeaders() {
  const headers = { 'X-PRG32-Kit': '1' };
  const user = $('meta[name="prg32-user"]').attr('content');
  if (user) headers['X-PRG32-User'] = user;
  return headers;
}

async function cartridgeBytes(cartridge) {
  const response = await fetch('/api/artifacts/' + encodeURIComponent(cartridge.id) + '/download', { headers: requestHeaders() });
  if (!response.ok) throw new Error('The compiled cartridge could not be downloaded (' + response.status + ').');
  const data = new Uint8Array(await response.arrayBuffer());
  if (data.length < 80 || String.fromCharCode(...data.slice(0, 4)) !== 'PRG2') {
    throw new Error('The selected artifact is not a PRG32 cartridge. Compile the project again.');
  }
  if (data.length > SLOT_SIZE) throw new Error('The cartridge is larger than a 128 KiB device slot.');
  const digest = Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256', data)))
    .map(byte => byte.toString(16).padStart(2, '0')).join('');
  if (!cartridge.sha256 || digest !== cartridge.sha256) {
    throw new Error('The compiled cartridge no longer matches its build record. Compile the project again.');
  }
  return { data, info: cartridgeInfo(data) };
}

async function openSession() {
  // choosePort() runs before any other await so the click still counts as
  // the user gesture that Web Serial requires. It reuses the one authorized
  // PRG32 (navigator.serial.getPorts()) or shows the chooser.
  const port = await choosePort(navigator.serial);
  const session = new ProtocolSession(port);
  await session.open();
  return session;
}

function logDevice(capabilities) {
  appendLog('Protocol: ' + capabilities.protocol);
  appendLog('Device firmware: ' + (capabilities.firmware || 'unknown') + ' (' + (capabilities.target || 'unknown target') + ')');
}

async function deployUsb() {
  const cartridge = selectedCartridge();
  const slot = $slot.val();
  const command = $command.val();
  if (!cartridge || cartridge.architecture !== 'esp32c6' || !SLOT_NAMES.includes(slot)) return;
  busy = true;
  ready();
  $log.text('').addClass('d-none');
  setProgress(0);
  $result.text('').addClass('d-none');
  let session = null;
  let phase = 'opening';
  try {
    $status.text(tr('js.deploy.usb_choose', 'Choose the PRG32 USB serial device.'));
    session = await openSession();
    phase = 'open';
    $status.text(tr('js.deploy.usb_preparing', 'Preparing the cartridge…'));
    const prepared = await cartridgeBytes(cartridge);
    $status.text(tr('js.deploy.usb_connecting', 'Negotiating PRG32 USB capabilities…'));
    const capabilities = await session.hello();
    logDevice(capabilities);
    // ABI, size, prg32-io-1.0 and capabilities.debug_supported are checked
    // here, before UPLOAD_BEGIN, so a refusal never erases the slot.
    const problems = cartridgeProblems(prepared.info, capabilities, command);
    if (problems.length) throw new Error(problems.join(' ') + ' ' + tr('js.deploy.usb_nothing_written', 'Nothing was written.'));
    appendLog('PRG32 cartridge: ' + prepared.info.name + ' (' + prepared.info.size + ' bytes, ABI ' + prepared.info.abiMajor + '.' + prepared.info.abiMinor + ')');
    appendLog('Destination: ' + slot + '; command: ' + command + '; chunk: ' + session.chunkSize() + ' bytes');
    $status.text(tr('js.deploy.usb_writing', 'Writing and verifying {slot}…', { slot }));
    phase = 'sending';
    const result = await session.upload(prepared.data, { name: prepared.info.name, slot, command }, (received, total) => setProgress(received * 100 / total));
    setProgress(100);
    appendLog('Device: ' + JSON.stringify(result));
    const finished = result.running
      ? tr('js.deploy.usb_running', '{slot} holds the cartridge and it is running.', { slot })
      : tr('js.deploy.usb_stored', '{slot} holds the cartridge. The PRG32 is back in setup.', { slot });
    $status.empty().append($('<span class="text-success">').text(finished));
  } catch (error) {
    showError(error, phase, slot);
  } finally {
    if (session) await session.close();
    busy = false;
    ready();
  }
}

async function retrievePerformance() {
  busy = true;
  ready();
  $result.text('').addClass('d-none');
  let session = null;
  let phase = 'opening';
  try {
    $status.text(tr('js.deploy.usb_choose', 'Choose the PRG32 USB serial device.'));
    session = await openSession();
    phase = 'open';
    const capabilities = await session.hello();
    logDevice(capabilities);
    if (!(capabilities.capabilities || []).includes('performance')) throw new Error('This device does not offer performance results over USB.');
    const text = await session.performance();
    $result.removeClass('d-none').text(JSON.stringify(JSON.parse(text), null, 2));
    $status.empty().append($('<span class="text-success">').text(tr('js.deploy.usb_performance_done', 'Performance results retrieved over USB.')));
  } catch (error) {
    showError(error, phase);
  } finally {
    if (session) await session.close();
    busy = false;
    ready();
  }
}

$confirm.on('change', ready);
$slot.add($command).on('change', () => { $confirm.prop('checked', false); ready(); });
$('#deployCartridge').on('change', () => { $confirm.prop('checked', false); ready(); });
$start.on('click', deployUsb);
$performance.on('click', retrievePerformance);
ready();
