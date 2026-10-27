// Direct USB deployment of one validated PRG32 cartridge (ADR-0020).
// The resident firmware receives the cartridge, displays transfer progress,
// verifies the slot, and launches it without resetting prototype1.
import { ProtocolSession } from './prg32_usb_protocol.js';

const SLOT_SIZE = 128 * 1024;
const SLOT_NAMES = Object.freeze(['cart0', 'cart1', 'cart2', 'cart3', 'cart4', 'cart5', 'cart6', 'cart7']);

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

function ready() {
  const cartridge = selectedCartridge();
  const supported = Boolean(window.isSecureContext && navigator.serial);
  $('#usbDeployUnsupported').toggleClass('d-none', supported);
  $start.prop('disabled', busy || !supported || !$confirm.is(':checked') || !cartridge || cartridge.architecture !== 'esp32c6');
  $performance.prop('disabled', busy || !supported);
}

function appendLog(text) {
  $log.removeClass('d-none').text(($log.text() + String(text) + '\n').slice(-12000));
}

function setProgress(percent) {
  const value = Math.max(0, Math.min(100, Math.round(percent)));
  $progress.removeClass('d-none').attr('aria-valuenow', value).find('.progress-bar').css('width', value + '%');
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
  const nameBytes = data.slice(40, 72);
  const terminator = nameBytes.indexOf(0);
  const name = new TextDecoder().decode(terminator < 0 ? nameBytes : nameBytes.slice(0, terminator)).trim();
  return { data, bytes: data.length, name: name || 'PRG32 cartridge' };
}

async function openSession() {
  const authorized = await navigator.serial.getPorts();
  const port = authorized.length === 1 ? authorized[0] : await navigator.serial.requestPort();
  const session = new ProtocolSession(port);
  await session.open();
  return session;
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
  $status.text(tr('js.deploy.usb_preparing', 'Preparing the cartridge…'));
  let session = null;
  try {
    const prepared = await cartridgeBytes(cartridge);
    $status.text(tr('js.deploy.usb_choose', 'Choose the PRG32 USB serial device.'));
    session = await openSession();
    $status.text(tr('js.deploy.usb_connecting', 'Negotiating PRG32 USB capabilities…'));
    const capabilities = await session.hello();
    if (capabilities.protocol !== 'prg32-io-1.0') throw new Error('The device does not support PRG32 USB protocol 1.0.');
    if (command === 'debug' && !capabilities.debug_supported) throw new Error('This physical PRG32 cannot instruction-debug cartridges. Choose PRG32-QT for USB debugging.');
    appendLog('Protocol: ' + capabilities.protocol);
    appendLog('PRG32 cartridge: ' + prepared.name + ' (' + prepared.bytes + ' bytes)');
    appendLog('Destination: ' + slot + '; command: ' + command);
    $status.text(tr('js.deploy.usb_writing', 'Writing and verifying {slot}…', { slot }));
    await session.upload(prepared.data, { name: prepared.name, slot, command }, (received, total) => setProgress(received * 100 / total));
    setProgress(100);
    $status.empty().append($('<span class="text-success">').text(tr('js.deploy.usb_finished', 'USB operation finished. The device verified the cartridge.')));
  } catch (error) {
    const message = error && error.name === 'NotFoundError' ? tr('js.deploy.usb_cancelled', 'No USB device was selected; nothing was written.')
      : (error && error.message ? error.message : String(error));
    $status.html('<span class="text-danger"></span>').find('span').text(message);
    appendLog(message);
  } finally {
    if (session) await session.close();
    busy = false;
    ready();
  }
}

async function retrievePerformance() {
  busy = true;
  ready();
  let session = null;
  try {
    $status.text('Choose the PRG32 USB serial device to retrieve performance results.');
    session = await openSession();
    const capabilities = await session.hello();
    if (!(capabilities.capabilities || []).includes('performance')) throw new Error('This device does not offer performance results over USB.');
    const text = await session.performance();
    $result.removeClass('d-none').text(JSON.stringify(JSON.parse(text), null, 2));
    $status.empty().append($('<span class="text-success">').text('Performance results retrieved over USB.'));
  } catch (error) {
    const message = error && error.name === 'NotFoundError' ? 'No USB device was selected.' : (error.message || String(error));
    $status.html('<span class="text-danger"></span>').find('span').text(message);
    appendLog(message);
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
