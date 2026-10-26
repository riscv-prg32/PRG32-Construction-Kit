// Direct USB deployment of one validated PRG32 cartridge (ADR-0020).
// The ESP32-C6 ROM bootloader writes only the selected 128 KiB cartridge
// partition. Firmware, settings, scores, and every other slot stay untouched.
import { ESPLoader, Transport } from '/static/vendor/esptool-js/0.7.0/bundle.js';

const SLOT_SIZE = 128 * 1024;
const SLOT_OFFSETS = Object.freeze({
  cart0: 0x210000, cart1: 0x230000, cart2: 0x250000, cart3: 0x270000,
  cart4: 0x290000, cart5: 0x2b0000, cart6: 0x2d0000, cart7: 0x2f0000
});

const $start = $('#usbDeployStart');
const $confirm = $('#usbDeployConfirm');
const $slot = $('#usbDeploySlot');
const $status = $('#usbDeployStatus');
const $log = $('#usbDeployLog');
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
  const image = new Uint8Array(SLOT_SIZE);
  image.fill(0xff);
  image.set(data);
  return { image, bytes: data.length };
}

async function deployUsb() {
  const cartridge = selectedCartridge();
  const slot = $slot.val();
  if (!cartridge || cartridge.architecture !== 'esp32c6' || !SLOT_OFFSETS[slot]) return;
  busy = true;
  ready();
  $log.text('').addClass('d-none');
  setProgress(0);
  $status.text(tr('js.deploy.usb_preparing', 'Preparing the cartridge…'));
  let transport = null;
  try {
    const prepared = await cartridgeBytes(cartridge);
    $status.text(tr('js.deploy.usb_choose', 'Choose the PRG32 USB serial device.'));
    const port = await navigator.serial.requestPort();
    transport = new Transport(port, true);
    const terminal = { clean() {}, write(text) { appendLog(text); }, writeLine(text) { appendLog(text); } };
    const loader = new ESPLoader({ transport, baudrate: 460800, romBaudrate: 115200, terminal, debugLogging: false });
    $status.text(tr('js.deploy.usb_connecting', 'Connecting to the ESP32-C6 bootloader…'));
    const chip = await loader.main();
    if (!String(chip).toUpperCase().includes('ESP32-C6')) {
      throw new Error('This is ' + chip + ', not the ESP32-C6 used by PRG32. Nothing was written.');
    }
    appendLog('PRG32 cartridge: ' + prepared.bytes + ' bytes');
    appendLog(slot + ': 0x' + SLOT_OFFSETS[slot].toString(16) + '–0x' + (SLOT_OFFSETS[slot] + SLOT_SIZE - 1).toString(16));
    $status.text(tr('js.deploy.usb_writing', 'Writing and verifying {slot}…', { slot }));
    await loader.writeFlash({
      fileArray: [{ data: prepared.image, address: SLOT_OFFSETS[slot] }],
      flashMode: 'keep', flashFreq: 'keep', flashSize: 'detect', eraseAll: false, compress: true,
      reportProgress(_file, written, total) { setProgress(total ? written * 100 / total : 0); }
    });
    setProgress(100);
    $status.empty().append($('<span class="text-success">').text(tr('js.deploy.usb_finished', 'USB deployment finished. The device is restarting; choose the cartridge from its menu if it was not already selected.')));
    await loader.after('hard_reset');
  } catch (error) {
    const message = error && error.name === 'NotFoundError' ? tr('js.deploy.usb_cancelled', 'No USB device was selected; nothing was written.')
      : (error && error.message ? error.message : String(error));
    $status.html('<span class="text-danger"></span>').find('span').text(message);
    appendLog(message);
  } finally {
    if (transport) {
      try { await transport.disconnect(); } catch (_error) { /* the reset may already close it */ }
    }
    busy = false;
    ready();
  }
}

$confirm.on('change', ready);
$slot.on('change', () => { $confirm.prop('checked', false); ready(); });
$('#deployCartridge').on('change', () => { $confirm.prop('checked', false); ready(); });
$start.on('click', deployUsb);
ready();
