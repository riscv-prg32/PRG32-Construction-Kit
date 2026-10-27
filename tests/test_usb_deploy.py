"""The browser-to-USB cartridge path writes one slot, never the firmware."""

from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SCRIPT = (ROOT / "static/js/usb_deploy.js").read_text(encoding="utf-8")
PROTOCOL = (ROOT / "static/js/prg32_usb_protocol.js").read_text(encoding="utf-8")


def test_usb_deploy_uses_the_eight_canonical_cartridge_slots_only():
    expected = {
        "cart0": "0x210000", "cart1": "0x230000", "cart2": "0x250000", "cart3": "0x270000",
        "cart4": "0x290000", "cart5": "0x2b0000", "cart6": "0x2d0000", "cart7": "0x2f0000",
    }
    partitions = (ROOT.parent / "PRG32/profiles/partitions_prg32.csv").read_text(encoding="utf-8")
    for slot, offset in expected.items():
        assert f"{slot}," in partitions and offset in partitions
        assert f'"{slot}"' in SCRIPT or f"'{slot}'" in SCRIPT
    assert "SLOT_SIZE = 128 * 1024" in SCRIPT
    assert "SLOT_NAMES.includes(slot)" in SCRIPT


def test_usb_deploy_validates_before_writing_through_resident_firmware():
    assert "crypto.subtle.digest('SHA-256', data)" in SCRIPT
    assert "String.fromCharCode(...data.slice(0, 4)) !== 'PRG2'" in SCRIPT
    assert "cartridge.architecture !== 'esp32c6'" in SCRIPT
    assert "prg32-io-1.0" in SCRIPT
    assert "port.open({ baudRate: 115200" in PROTOCOL
    assert "navigator.serial.getPorts()" in SCRIPT
    assert "MESSAGE.UPLOAD_BEGIN" in PROTOCOL
    assert "MESSAGE.UPLOAD_DATA" in PROTOCOL
    assert "MESSAGE.UPLOAD_END" in PROTOCOL
    assert "crc32(data)" in PROTOCOL


def test_usb_deploy_exposes_run_performance_and_capability_checked_debugging():
    template = (ROOT / "templates/deploy.html").read_text(encoding="utf-8")
    for command in ("store", "run", "performance", "debug"):
        assert f'value="{command}"' in template
    assert "capabilities.debug_supported" in SCRIPT
    assert "before it\nerases" in (ROOT / "docs/deploy.md").read_text(encoding="utf-8")
    assert "MESSAGE.PERFORMANCE_GET" in PROTOCOL
    assert 'id="usbPerformanceGet"' in template


def test_usb_deploy_requires_an_explicit_slot_replacement_confirmation():
    template = (ROOT / "templates/deploy.html").read_text(encoding="utf-8")
    assert 'id="usbDeployConfirm"' in template
    assert 'id="usbDeployStart" disabled' in template
    assert "$confirm.is(':checked')" in SCRIPT


def test_usb_deploy_docs_preserve_the_fixed_prototype1_pinout():
    documentation = (ROOT / "docs/deploy.md").read_text(encoding="utf-8")
    assert "Down button uses GPIO0" in documentation
    assert "GPIO12/GPIO13 remain available" in documentation
    assert "onboard RGB LED also shares GPIO8" in documentation
    assert "with LCD D/C" in documentation
    assert "Do not\nmove the canonical prototype1 pins" in documentation
    assert "detects the first `prg32-io-1.0` frame automatically" in documentation
    assert "ROM bootloader remains a firmware-recovery path" in documentation
