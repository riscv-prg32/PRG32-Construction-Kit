"""The browser-to-USB cartridge path writes one slot, never the firmware."""

from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SCRIPT = (ROOT / "static/js/usb_deploy.js").read_text(encoding="utf-8")


def test_usb_deploy_uses_the_canonical_cartridge_partitions_only():
    expected = {
        "cart0": "0x210000", "cart1": "0x230000", "cart2": "0x250000", "cart3": "0x270000",
        "cart4": "0x290000", "cart5": "0x2b0000", "cart6": "0x2d0000", "cart7": "0x2f0000",
    }
    partitions = (ROOT.parent / "PRG32/profiles/partitions_prg32.csv").read_text(encoding="utf-8")
    for slot, offset in expected.items():
        assert f"{slot}," in partitions and offset in partitions
        assert f"{slot}: {offset}" in SCRIPT
    assert "SLOT_SIZE = 128 * 1024" in SCRIPT
    assert "eraseAll: false" in SCRIPT


def test_usb_deploy_validates_before_writing_and_uses_the_local_vendor_bundle():
    assert "crypto.subtle.digest('SHA-256', data)" in SCRIPT
    assert "String.fromCharCode(...data.slice(0, 4)) !== 'PRG2'" in SCRIPT
    assert "cartridge.architecture !== 'esp32c6'" in SCRIPT
    assert "ESP32-C6" in SCRIPT
    assert "from '/static/vendor/esptool-js/0.7.0/bundle.js'" in SCRIPT
    assert (ROOT / "static/vendor/esptool-js/0.7.0/bundle.js").is_file()


def test_usb_deploy_requires_an_explicit_slot_replacement_confirmation():
    template = (ROOT / "templates/deploy.html").read_text(encoding="utf-8")
    assert 'id="usbDeployConfirm"' in template
    assert 'id="usbDeployStart" disabled' in template
    assert "$confirm.is(':checked')" in SCRIPT


def test_usb_deploy_docs_preserve_the_fixed_prototype1_pinout():
    documentation = (ROOT / "docs/deploy.md").read_text(encoding="utf-8")
    assert "GPIO13 is both the Down button and native USB D+" in documentation
    assert "onboard RGB LED also shares GPIO8" in documentation
    assert "with LCD D/C" in documentation
    assert "Do not\nmove either canonical prototype1 pin" in documentation
    assert "save it as the default" in documentation
