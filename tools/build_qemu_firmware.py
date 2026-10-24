"""Make the PRG32 firmware folder that Deploy boots in QEMU (PRG32_QEMU_FIRMWARE, docs/deploy.md).

    . $HOME/esp-idf/export.sh
    python3 tools/build_qemu_firmware.py --sdk ../PRG32 --revision 679dfb5 --out data/qemu-firmware

    python3 tools/build_qemu_firmware.py --sdk ../PRG32 --from-build ../PRG32/build-qemu --out DIR

The first form builds the firmware with ESP-IDF from a clean clone of --sdk at --revision (the SDK
checkout itself is never changed), with the SDK's own QEMU profile. The second takes a folder an
``idf.py`` QEMU build already made (it must hold qemu_flash.bin) and only describes it; --sdk is
then the checkout that build came from, at the revision it was built from.

The folder gets qemu_flash.bin, qemu_efuse.bin, PRG32.elf, sdkconfig and prg32-firmware.json: the
SDK revision, the firmware's cartridge ABI (from that revision's prg32/abi/abi_generated.py), its
cartridge RAM (sdkconfig), the cartridge slots (profiles/partitions_prg32.csv), the SHA-256 of the
flash image (Deploy refuses an image that no longer matches) and the two firmware symbols Deploy
reads the screen with. Nothing in it comes from a guess: a missing piece stops the tool.
"""

from __future__ import annotations

import argparse
import csv
import datetime
import hashlib
import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

CART_MAX_SIZE = 64 * 1024        # the PRG32 hardware limit (SDK runtime_handler.ensure_cart_max_size)


def run(command: list[str], cwd: Path) -> str:
    return subprocess.run(command, cwd=cwd, check=True, capture_output=True, text=True).stdout


def build(sdk: Path, revision: str, work: Path) -> Path:
    source = work / "prg32"
    run(["git", "clone", "-q", "--no-hardlinks", str(sdk.resolve()), str(source)], work)
    run(["git", "checkout", "-q", revision], source)
    defaults = "profiles/sdkconfig.defaults;profiles/sdkconfig.defaults.qemu"
    for action in (["set-target", "esp32c3"], ["build"]):
        run(["idf.py", "-B", "build-qemu", "-D", "SDKCONFIG=build-qemu/sdkconfig", "-D", f"SDKCONFIG_DEFAULTS={defaults}",
             *action], source)
    folder = source / "build-qemu"
    esptool = ["esptool.py"] if shutil.which("esptool.py") else [sys.executable, "-m", "esptool"]
    run([*esptool, "--chip=esp32c3", "merge_bin", "--output=qemu_flash.bin", "--fill-flash-size=4MB", "@flash_args"], folder)
    return folder


def efuse_image(folder: Path, sdk: Path) -> Path:
    """The ESP32-C3 eFuse image QEMU needs (the SDK makes it with prg32.utilities.environment_check)."""
    target = folder / "qemu_efuse.bin"
    if not target.is_file():
        sys.path.insert(0, str(sdk))
        import os

        cwd = os.getcwd()
        try:
            os.chdir(folder.parent)
            from prg32.utilities.environment_check import ensure_qemu_efuse

            ensure_qemu_efuse()
        finally:
            os.chdir(cwd)
    if not target.is_file():
        raise SystemExit(f"no qemu_efuse.bin in {folder}")
    return target


def abi_of(sdk: Path) -> dict:
    spec = importlib.util.spec_from_file_location("abi_generated", sdk / "prg32" / "abi" / "abi_generated.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    features = 0
    for bit in module.FEATURE_BITS.values():
        features |= int(bit)
    return {"major": module.ABI_MAJOR, "minor": module.ABI_MINOR, "hash": module.ABI_HASH, "features": features,
            "compatible": list(module.COMPATIBLE_ABI_HASHES)}


def slots_of(sdk: Path) -> list[dict]:
    slots = []
    with (sdk / "profiles" / "partitions_prg32.csv").open() as table:
        for row in csv.reader(line for line in table if not line.lstrip().startswith("#")):
            if len(row) >= 5 and row[0].strip().startswith("cart"):
                size = row[4].strip()
                slots.append({"name": row[0].strip(), "offset": int(row[3].strip(), 0),
                              "size": int(size[:-1]) * 1024 if size.endswith("K") else int(size, 0)})
    if not slots:
        raise SystemExit("profiles/partitions_prg32.csv has no cartridge slots")
    return slots


def sdkconfig_value(path: Path, name: str) -> str | None:
    for line in path.read_text().splitlines():
        if line.startswith(name + "="):
            return line.split("=", 1)[1].strip().strip('"')
    return None


def symbols_of(elf: Path) -> dict:
    nm = shutil.which("riscv32-esp-elf-nm")
    if not nm:
        return {}
    found = {}
    for line in run([nm, str(elf)], elf.parent).splitlines():
        parts = line.split()
        if len(parts) == 3 and parts[2] in ("g_fb", "prg32_gfx_present"):
            found[parts[2]] = int(parts[0], 16)
    return found


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--sdk", type=Path, required=True, help="a PRG32 SDK checkout")
    parser.add_argument("--revision", help="build this SDK revision (needs ESP-IDF)")
    parser.add_argument("--from-build", type=Path, help="describe this existing QEMU build folder instead")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    if bool(args.revision) == bool(args.from_build):
        parser.error("give --revision (build) or --from-build (describe), not both")
    with tempfile.TemporaryDirectory() as temp:
        if args.revision:
            folder = build(args.sdk, args.revision, Path(temp))
            sdk = folder.parent
        else:
            folder, sdk = args.from_build.resolve(), args.sdk.resolve()
        for name in ("qemu_flash.bin", "PRG32.elf", "sdkconfig"):
            if not (folder / name).is_file():
                raise SystemExit(f"no {name} in {folder}")
        args.out.mkdir(parents=True, exist_ok=True)
        for name in ("qemu_flash.bin", "PRG32.elf", "sdkconfig"):
            shutil.copyfile(folder / name, args.out / name)
        shutil.copyfile(efuse_image(folder, sdk), args.out / "qemu_efuse.bin")
        commit = run(["git", "rev-parse", "HEAD"], sdk).strip()
        ram_kib = sdkconfig_value(folder / "sdkconfig", "CONFIG_PRG32_CART_RAM_KIB")
        if ram_kib is None:
            raise SystemExit("sdkconfig has no CONFIG_PRG32_CART_RAM_KIB")
        stereo = sdkconfig_value(folder / "sdkconfig", "CONFIG_PRG32_AUDIO_MODE_STEREO") == "y"
        manifest = {
            "format": "prg32-qemu-firmware-1",
            "sdk_commit": commit,
            "firmware_version": commit[:7],
            "made_at": datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat(),
            "made_by": "tools/build_qemu_firmware.py " + ("--revision " + args.revision if args.revision else "--from-build"),
            "idf_version": sdkconfig_value(folder / "sdkconfig", "CONFIG_IDF_INIT_VERSION") or "",
            "abi": abi_of(sdk),
            "cart_ram_size": int(ram_kib) * 1024,
            "cart_max_size": CART_MAX_SIZE,
            "slots": slots_of(sdk),
            "audio_chunk_bytes": 1764 if stereo else 882,
            "flash_sha256": hashlib.sha256((args.out / "qemu_flash.bin").read_bytes()).hexdigest(),
            "symbols": symbols_of(args.out / "PRG32.elf"),
        }
    (args.out / "prg32-firmware.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"Wrote {args.out}/prg32-firmware.json (SDK {commit[:7]}, ABI 0x{manifest['abi']['hash']:08x})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
