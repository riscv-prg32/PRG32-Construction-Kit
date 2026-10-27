# Deploy: put your game on a PRG32

**Deploy** (in the menu of an open project) puts a compiled PRG32 cartridge on the class's PRG32
console, in PRG32-QT, or in QEMU on the kit's server, and shows you that it started.

Only a PRG32 console is a physical device. A game that runs in PRG32-QT or QEMU works in an
emulator: that is good to know, but it does not prove that the game works on the console. The
page and every record say which one it was.

## For students

1. In the editor, press **Compile**. Deploy uses the compiled cartridge, never unsaved work. If
   you change the project afterwards, Deploy asks you to compile again.
2. Open **Deploy**. Your project and its newest cartridge are already chosen.
3. Choose the **target** and press **Look at it**. You see who the target is (its firmware and
   the cartridge ABI it runs) and what each **slot** holds now. A slot that the cartridge does
   not fit in cannot be chosen.
4. Choose a slot. What is in it will be replaced, so pick one nobody needs. Tick **Replace what
   is in cart3 (…) on …** and press **Deploy**.
5. Watch the steps: checking the target, sending, starting, checking that it runs. At the end
   you see a screenshot from the target. **Cancel** stops before the next step.

If something goes wrong, the page says why and what the target holds now. For example, "cart3
holds this cartridge, but it did not start" or "Nothing was sent: the target is as it was".

| You see | What to do |
| --- | --- |
| The project changed after this cartridge was compiled | press **Compile**, then deploy again |
| holds something else now than when you looked | somebody used that slot meanwhile: **Look at it** again |
| The target is not the one you looked at | its firmware changed: **Look at it** again |
| The cartridge needs ABI … / was built for ABI … | the target's firmware is from another PRG32 version: ask your teacher |
| does not fit / takes at most … | the game is too big for that target |
| The target does not answer | is it switched on, and on the same network as the kit? |

## For teachers and administrators

### Direct USB from the browser

Chrome and Edge can deploy the selected `esp32c6` PRG32 cartridge directly to an ESP32-C6 over
USB. On the Deploy page, choose the project and compiled cartridge, then use **USB device**:

1. choose `cart0` through `cart7`, select **store**, **run**, **performance**, or **debug**, and
   confirm that the slot may be replaced;
2. press **Connect and deploy over USB** and choose the PRG32 serial device in the browser prompt;
3. the page verifies the artifact SHA-256 and `PRG2` header, negotiates device capabilities, and
   sends the cartridge metadata and CRC-protected payload;
4. the firmware detects the first `prg32-io-1.0` frame automatically, shows the cartridge name,
   slot and progress bar, verifies the slot, reports success or failure, and returns to setup after
   **store**. **run** and **performance** start the cartridge.

Use **Retrieve performance results** to read the latest performance JSON through the same USB
connection. **debug** starts the cartridge under PRG32-QT's debugger. Physical PRG32 firmware
advertises that instruction debugging is unavailable, so the page refuses the operation before it
erases the chosen slot and explains that PRG32-QT is required.

Web Serial requires HTTPS, except that browsers also allow `localhost`. The normal USB path uses a
small receiver in the resident PRG32 firmware and does not replace the firmware, settings, scores or
other cartridges. `prg32-io-1.0` uses self-synchronising 24-byte binary headers, request IDs and
CRC-32 on every payload. The firmware accepts only `cart0` through `cart7`, bounds the payload to the
partition, requires ordered chunks, and launches it only after the normal cartridge validator succeeds.

On the current `prototype1` profile, the Down button uses GPIO0 so GPIO12/GPIO13 remain available to
native USB Serial/JTAG. The ESP32-C6 ROM bootloader remains a firmware-recovery path, but it cannot
draw cartridge upload progress. The onboard RGB LED also shares GPIO8
with LCD D/C: its cyan boot flashes are intentional, while brief green or white flashes during display
updates are an unavoidable electrical side effect and do not indicate a failed deployment. Do not
move the canonical prototype1 pins to hide these effects.

The framing and message definitions are maintained in the PRG32 SDK's
[`docs/software/usb_protocol.md`](../../PRG32/docs/software/usb_protocol.md). The Construction Kit
copies the wire contract, but delegates cartridge validation and execution policy to the device.

The browser library is pinned in `static/vendor/` and the page makes no CDN request.

Register each target once, at the bottom of the Deploy page (administrators only):

- **PRG32 console**: its Wi-Fi address, usually `http://192.168.4.1`. The computer that runs
  the kit must be on the console's network (join its Wi-Fi).
- **PRG32-QT**: `http://<the computer>:8080` (PRG32-QT offers the console's web API there).

The kit talks only to these addresses, never to one a student types. Only consoles and
PRG32-QT computers can be registered.

**QEMU on the server** (operators): build the firmware folder once, then point the kit at it.
The tool uses the SDK's QEMU profile with one change, `tools/qemu/sdkconfig.deploy`: the firmware
boots the stored cartridge instead of its setup menu, so no key needs pressing.

```bash
. $HOME/esp-idf/export.sh
python3 tools/build_qemu_firmware.py --sdk ../PRG32 --revision 679dfb5 --out data/qemu-firmware
```

```bash
PRG32_QEMU_FIRMWARE=data/qemu-firmware python3 app.py
```

`PRG32_QEMU` names Espressif's `qemu-system-riscv32` (default: the one under `~/.espressif`), and
`PRG32_QEMU_GDB` its `riscv32-esp-elf-gdb`, which is used for screenshots. One QEMU runs at a
time. Each deployment boots a fresh copy of the firmware with the cartridge in `cart0`, so
nothing is overwritten.

## What is checked, every time

Before anything is sent:

- the cartridge is one this kit built, and its file still has the SHA-256 recorded at build time;
- it was built from the project as it is saved now;
- the target runs this architecture (console: `esp32c6`, QEMU: `qemu`, PRG32-QT: both);
- the target is the one you looked at, and the slot holds what you saw;
- the target's ABI (major version, ABI hash, features) accepts the cartridge, and the cartridge
  fits in its size and RAM limits.

Then the cartridge is sent (a broken connection is tried again twice). The slot is started, and
the target must report this cartridge running, by name and code size, with frames advancing.

## Recording evidence

`tools/deploy_evidence.py` deploys the Pong example to a real target through these same API
routes. It runs the refusals above against that target (no slot, slot changed, stale build,
changed file, wrong architecture), then deploys for real. It keeps `record.json` and the
screenshot:

```bash
python3 tools/deploy_evidence.py --prg32qt http://127.0.0.1:8080 --slot cart3 --out docs/evidence/deploy/DATE-prg32qt
```

Recorded runs: [QEMU](evidence/deploy/2026-10-24-qemu/record.json) and
[PRG32-QT](evidence/deploy/2026-10-24-prg32qt/record.json), both 2026-10-24. No PRG32 console
was available, so there is no physical-device record yet.

See also [delivery.md](delivery.md) (other ways to get a cartridge onto a PRG32) and
[ADR-0028](adr/0028-one-deploy-tool.md).
