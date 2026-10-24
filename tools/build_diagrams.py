"""Draw the architecture diagrams in docs/figures/ from the descriptions below (DOC-02).

    python3 tools/build_diagrams.py           # write the SVG files
    python3 tools/build_diagrams.py --check   # exit 1 if a file differs from what this script draws

Each diagram is plain data: boxes, arrows and trust boundaries. The script writes
deterministic SVG with a <title> and a <desc> (the text equivalent), so the pictures can be
reviewed as text, rebuilt after a change, and checked in CI (tools/check_docs.py and
docs/figures/manifest.json). Edit the data here, never the SVG files.
"""

from __future__ import annotations

import sys
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FIGURES = ROOT / "docs" / "figures"

INK, MUTED, LINE = "#0f172a", "#475569", "#334155"
FILLS = {
    "browser": ("#e0f2fe", "#0369a1"), "server": ("#ecfccb", "#4d7c0f"), "external": ("#f5f3ff", "#6d28d9"),
    "data": ("#fff7ed", "#c2410c"), "check": ("#fef9c3", "#a16207"), "plain": ("#f8fafc", "#475569"),
    "unverified": ("#f1f5f9", "#94a3b8"),
}
TAGS = {"personal": "#c2410c", "secret": "#b91c1c", "verified": "#15803d", "unverified": "#64748b",
        "unsupported": "#64748b", "retention": "#1d4ed8"}


class Svg:
    def __init__(self, width: int, height: int, title: str, desc: str):
        self.width, self.height, self.title, self.desc = width, height, title, desc
        self.parts: list[str] = []

    def zone(self, x, y, w, h, label, kind):
        fill, stroke = FILLS[kind]
        self.parts.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="16" fill="{fill}" fill-opacity="0.45" '
                          f'stroke="{stroke}" stroke-width="2" stroke-dasharray="8 6"/>')
        self.parts.append(f'<text x="{x + 14}" y="{y + 26}" font-size="17" font-weight="bold" fill="{stroke}">{escape(label)}</text>')

    def box(self, x, y, w, h, title, lines=(), kind="plain", tags=()):
        fill, stroke = FILLS[kind]
        dash = ' stroke-dasharray="4 4"' if kind == "unverified" else ""
        self.parts.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="10" fill="{fill}" stroke="{stroke}" '
                          f'stroke-width="1.5"{dash}/>')
        self.parts.append(f'<text x="{x + 10}" y="{y + 21}" font-size="14" font-weight="bold" fill="{INK}">{escape(title)}</text>')
        for index, line in enumerate(lines):
            self.parts.append(f'<text x="{x + 10}" y="{y + 40 + 17 * index}" font-size="12.5" fill="{MUTED}">{escape(line)}</text>')
        tag_x = x + w - 8
        for tag in reversed(tags):
            width = 7.2 * len(tag) + 12
            tag_x -= width
            self.parts.append(f'<rect x="{tag_x:.0f}" y="{y + 7}" width="{width:.0f}" height="17" rx="8" fill="{TAGS[tag]}"/>')
            self.parts.append(f'<text x="{tag_x + width / 2:.0f}" y="{y + 19}" font-size="11" text-anchor="middle" '
                              f'fill="#ffffff">{escape(tag)}</text>')
            tag_x -= 4

    def arrow(self, points, label="", both=False, dashed=False, label_at=None):
        path = " ".join(f"{'M' if index == 0 else 'L'}{x},{y}" for index, (x, y) in enumerate(points))
        start = ' marker-start="url(#arrow)"' if both else ""
        dash = ' stroke-dasharray="6 5"' if dashed else ""
        self.parts.append(f'<path d="{path}" fill="none" stroke="{LINE}" stroke-width="2"{dash} marker-end="url(#arrow)"{start}/>')
        if label:
            (x1, y1), (x2, y2) = points[0], points[-1]
            lx, ly = label_at or ((x1 + x2) / 2, (y1 + y2) / 2 - 7)
            self.parts.append(f'<text x="{lx:.0f}" y="{ly:.0f}" font-size="12" text-anchor="middle" fill="{INK}" '
                              f'paint-order="stroke" stroke="#ffffff" stroke-width="4">{escape(label)}</text>')

    def text(self, x, y, value, size=13, anchor="start", bold=False, color=MUTED):
        weight = ' font-weight="bold"' if bold else ""
        self.parts.append(f'<text x="{x}" y="{y}" font-size="{size}" text-anchor="{anchor}" fill="{color}"{weight}>'
                          f'{escape(value)}</text>')

    def render(self) -> str:
        head = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {self.width} {self.height}" role="img" '
                f'aria-labelledby="title desc" font-family="Helvetica, Arial, sans-serif">\n'
                f'  <title id="title">{escape(self.title)}</title>\n  <desc id="desc">{escape(self.desc)}</desc>\n'
                '  <defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" '
                f'orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="{LINE}"/></marker></defs>\n'
                f'  <rect width="{self.width}" height="{self.height}" fill="#ffffff"/>\n')
        return head + "".join(f"  {part}\n" for part in self.parts) + "</svg>\n"


def legend(svg: Svg, x: int, y: int) -> None:
    svg.text(x, y, "Legend:", bold=True, color=INK)
    svg.text(x + 64, y, "dashed frame = trust boundary;  dashed box = not verified or unsupported;")
    tag_x = x + 520
    for tag in ("personal", "secret", "retention", "verified", "unverified"):
        width = 7.2 * len(tag) + 12
        svg.parts.append(f'<rect x="{tag_x:.0f}" y="{y - 12}" width="{width:.0f}" height="17" rx="8" fill="{TAGS[tag]}"/>')
        svg.parts.append(f'<text x="{tag_x + width / 2:.0f}" y="{y}" font-size="11" text-anchor="middle" fill="#ffffff">{tag}</text>')
        tag_x += width + 8


def architecture() -> Svg:
    desc = ("Three trust zones. The student's browser runs the one IDE (Blocks, C or assembly projects, with Sprite Lab "
            "and AudioStudio as tabs of the open project and the simulator on the right), the Player and the account "
            "pages; the PRG32-QT core and the firmware audio engine as WebAssembly with the debugger; a JavaScript IR "
            "simulator only when the server has no toolchain; guest games in IndexedDB; a service worker caching static "
            "files only. The kit server (the operator's host) runs Flask with a signed session cookie, authorization and "
            "the privacy workflows; validators for Blocks IR, C and assembly; deterministic C, RV32IM assembly and "
            "AUD0 generators; the PRG32 toolchain in a bubblewrap sandbox with one folder per build, where Run builds "
            "keep nothing; SQLite; build and artifact folders; and backups. External services are separate parties: "
            "the school identity provider, Google Drive, OneDrive or GitHub by the person's consent, the Cartridge Store "
            "(reviewed publishing; optional shared accounts with one private username matched by email and a separate "
            "public handle), an SMTP provider; cartridges go to PRG32-QT (verified through its web API), a PRG32 console "
            "(not verified) or PRG32-iOS (unsupported).")
    svg = Svg(1240, 815, "PRG32 Construction Kit architecture: components and trust boundaries", desc)
    svg.text(620, 34, "Components and trust boundaries", size=22, anchor="middle", bold=True, color=INK)
    svg.zone(20, 60, 380, 690, "Student's browser (untrusted client)", "browser")
    svg.box(38, 100, 344, 82, "Pages", ["one IDE: Blocks, C or assembly, simulator on the", "right, Sprite Lab + AudioStudio tabs; Player, Account"], "browser")
    svg.box(38, 194, 344, 82, "Editors and offline checks", ["Blockly, Monaco, language index", "(only what the validators accept)"], "browser")
    svg.box(38, 288, 344, 100, "WebAssembly runtime", ["PRG32-QT core (RV32IMAC) + firmware audio engine", "8 voices, ADSR, stereo, one frame clock", "debugger: breakpoints, source and block maps"], "browser", ("verified",))
    svg.box(38, 400, 344, 64, "JavaScript IR simulator", ["only without a toolchain; the offline page"], "browser")
    svg.box(38, 476, 344, 82, "IndexedDB", ["guest games, unsaved work", "never sent for guests; cleared by the person"], "data", ("personal",))
    svg.box(38, 570, 344, 64, "Service worker", ["static files only, never signed-in pages"], "browser")
    svg.box(38, 646, 344, 82, "Session cookie (signed)", ["account id, session number, sign-in time", "ends a fixed time after sign-in"], "data", ("personal",))

    svg.zone(430, 60, 400, 690, "Kit server (operator's host)", "server")
    svg.box(448, 100, 364, 82, "Flask app", ["sign-in, roles, ownership, quotas, CSP, CSRF", "privacy: export, requests, erasure, notices"], "server")
    svg.box(448, 194, 364, 64, "Validators (before anything is compiled)", ["Blocks -> game IR, Advanced C, handwritten asm"], "check")
    svg.box(448, 270, 364, 82, "Deterministic generators", ["C and RV32IM assembly with explanations,", "AudioStudio -> AUD0 block, source maps"], "server")
    svg.box(448, 364, 364, 82, "Build sandbox", ["PRG32 toolchain in bubblewrap + seccomp, no", "network, one <build_id>/ folder; Run keeps nothing"], "server")
    svg.box(448, 458, 364, 82, "SQLite", ["accounts, projects, history, audit log (365 d),", "notice records, request register"], "data", ("personal", "secret"))
    svg.box(448, 552, 364, 82, "Files", ["builds/<build_id>/ (newest 10 per project),", "artifacts/ (uploads, AudioStudio samples)"], "data", ("personal",))
    svg.box(448, 646, 364, 82, "Backups", ["database + folders + secret key", "35 days, prune; erasures re-applied"], "data", ("personal", "secret", "retention"))

    svg.zone(860, 60, 360, 690, "External services (separate parties)", "external")
    svg.box(878, 100, 324, 82, "School identity provider", ["OIDC + PKCE or SAML; keeps issuer,", "subject, email (live: Keycloak)"], "external", ("verified",))
    svg.box(878, 194, 324, 82, "Drive, OneDrive, GitHub", ["own folder or repository, by consent;", "tokens sealed; no live tenant yet"], "unverified", ("unverified",))
    svg.box(878, 288, 324, 82, "PRG32 Cartridge Store", ["reviewed publishing; shared username (by", "email), public handle; live: loopback Store"], "external", ("verified",))
    svg.box(878, 382, 324, 64, "SMTP provider", ["sign-up and password emails"], "external")
    svg.box(878, 458, 324, 82, "PRG32-QT", ["cartridges through its web API,", "integrity-checked delivery"], "external", ("verified",))
    svg.box(878, 552, 324, 64, "PRG32 console (ESP32-C6)", ["download works; no recorded delivery"], "unverified", ("unverified",))
    svg.box(878, 628, 324, 64, "PRG32-iOS", ["unsupported (ADR-0020)"], "unverified", ("unsupported",))

    svg.arrow([(382, 141), (448, 141)], "HTTPS", both=True, label_at=(415, 132))
    svg.arrow([(448, 405), (415, 405), (415, 338), (382, 338)], "cartridge", label_at=(415, 398))
    svg.arrow([(812, 120), (878, 120)], "OIDC", both=True, label_at=(845, 112))
    svg.arrow([(812, 150), (878, 220)], "OAuth", both=True, label_at=(858, 176))
    svg.arrow([(812, 311), (878, 325)], "publish", label_at=(845, 304))
    svg.arrow([(812, 170), (840, 170), (840, 414), (878, 414)], "email", label_at=(858, 400))
    svg.arrow([(210, 728), (210, 772), (1040, 772), (1040, 750)], ".prg32 download (Player) or upload (delivery tool)",
              dashed=True, label_at=(625, 767))
    legend(svg, 24, 800)
    return svg


def pipeline() -> Svg:
    desc = ("Three ways to write a game: Blocks, Advanced C and handwritten assembly. Blocks are saved as JSON and turned "
            "into a validated game IR; C and assembly are checked by the validators before anything is compiled. The "
            "deterministic generators write C and, on request, RV32IM assembly that does exactly what the C does, with "
            "explanations; AudioStudio's sounds become an AUD0 block. The PRG32 toolchain in the build sandbox makes a "
            ".prg32 cartridge (a debug build adds source maps and is byte-identical). The cartridge runs in the browser's "
            "WebAssembly runtime with the debugger, on PRG32-QT, in QEMU, on a PRG32 console (not verified) or goes to "
            "the Cartridge Store as a reviewed bundle. Run makes the same cartridge for the IDE's simulator, also for "
            "guests, and keeps nothing; Compile keeps it for download and publishing (signed in).")
    svg = Svg(1240, 590, "From Blocks, C or assembly to a PRG32 cartridge", desc)
    svg.text(620, 34, "One validated, deterministic pipeline", size=22, anchor="middle", bold=True, color=INK)
    svg.text(620, 58, "The same saved project always gives the same IR, the same C and assembly, and the same cartridge.",
             anchor="middle")
    svg.box(20, 90, 200, 70, "Blocks", ["projects.blocks_json"], "browser")
    svg.box(20, 200, 200, 70, "Advanced C", ["game_json.source_c"], "browser")
    svg.box(20, 310, 200, 70, "Handwritten assembly", ["game_json.source_asm"], "browser")
    svg.box(20, 420, 200, 70, "AudioStudio", ["instruments, effects, tracker"], "browser")
    svg.box(270, 90, 210, 70, "Game IR", ["checked expressions"], "check")
    svg.box(270, 200, 210, 70, "C validator", ["portable ABI, no libc"], "check")
    svg.box(270, 310, 210, 70, "Assembly validator", ["directive allow-list"], "check")
    svg.box(270, 420, 210, 70, "AUD0 block", ["8 voices, stereo, deterministic"], "server")
    svg.box(530, 90, 230, 90, "Generators", ["deterministic C, RV32IM asm,", "per-block comments, source maps"], "server")
    svg.box(530, 250, 230, 110, "Build sandbox", ["PRG32 toolchain (rv32imc)", "bubblewrap, no network,", "one folder per build"], "server")
    svg.box(800, 250, 160, 110, ".prg32 cartridge", ["PRG2 header + code", "+ AUD0, SHA-256", "debug build: same bytes"], "data")
    svg.box(1005, 80, 225, 70, "Browser runtime", ["IDE simulator + debugger"], "browser", ("verified",))
    svg.box(1005, 170, 225, 70, "PRG32-QT", ["web API delivery"], "external", ("verified",))
    svg.box(1005, 260, 225, 70, "QEMU", ["ESP32-C3 firmware"], "external", ("verified",))
    svg.box(1005, 350, 225, 70, "PRG32 console", ["no recorded delivery"], "unverified", ("unverified",))
    svg.box(1005, 440, 225, 70, "Cartridge Store", ["reviewed bundle"], "external", ("verified",))
    for y in (125, 235, 345, 455):
        svg.arrow([(220, y), (270, y)])
    svg.arrow([(480, 125), (530, 130)])
    svg.arrow([(480, 235), (560, 250)])
    svg.arrow([(480, 345), (530, 330)])
    svg.arrow([(480, 455), (600, 455), (600, 360)])
    svg.arrow([(645, 180), (645, 250)])
    svg.arrow([(760, 305), (800, 305)])
    for y in (115, 205, 295, 385, 475):
        svg.arrow([(960, 305), (982, 305), (982, y), (1005, y)], dashed=(y == 385))
    svg.text(20, 540, "Never compiled: C an AI suggests, or anything a validator refuses. Students can open the generated C and assembly.",
             color=INK)
    svg.text(20, 568, "Run: the same cartridge for the IDE's simulator, also for guests; nothing is kept. "
             "Compile (signed in): kept for download and publishing.", color=INK)
    return svg


def data_flow() -> Svg:
    desc = ("Personal data, where it is kept and for how long. Guests: games stay in the browser (IndexedDB) until the "
            "person clears them. Students, teachers and administrators: account, classes and work in SQLite while the "
            "account exists; builds keep the newest 10 per project; deleted projects 30 days; the audit log 365 days; "
            "backups 35 days. Recipients by choice: the school identity provider (sign-in), Google Drive, OneDrive or "
            "GitHub (consent, the person's own folder or repository, possibly outside the EU), the Cartridge Store "
            "(publishing under a public handle; with shared accounts the private username, matched by email), "
            "an SMTP provider. Rights: download, correct, erase, restrict, object; erasure reaches tables, folders, files "
            "and cloud tokens, pseudonymises the audit log and is re-applied after a restore.")
    svg = Svg(1240, 620, "Personal data: who, where, how long, and who receives it", desc)
    svg.text(620, 34, "Personal data, retention and recipients", size=22, anchor="middle", bold=True, color=INK)
    svg.zone(20, 60, 260, 520, "People", "plain")
    svg.box(38, 100, 224, 70, "Guest", ["no account"], "plain")
    svg.box(38, 200, 224, 84, "Student", ["username, email, classes,", "games, sprites, sounds"], "plain", ("personal",))
    svg.box(38, 314, 224, 70, "Teacher / facilitator", ["reads class work only"], "plain", ("personal",))
    svg.box(38, 414, 224, 70, "Administrator", ["all actions audited"], "plain", ("personal",))
    svg.zone(310, 60, 520, 520, "Kept by the kit (controller: the school)", "server")
    svg.box(328, 100, 484, 64, "Browser IndexedDB (device only)", ["guest games; until the person clears them"], "data", ("personal",))
    svg.box(328, 176, 484, 82, "SQLite: accounts, classes, projects, history", ["while the account exists; trash 30 days;", "password and token hashes only"], "data", ("personal", "secret"))
    svg.box(328, 270, 484, 64, "Builds and artifacts", ["newest 10 builds per project; files go with them"], "data", ("personal", "retention"))
    svg.box(328, 346, 484, 64, "Audit log and request register", ["365 days; erasure pseudonymises the person"], "data", ("personal", "retention"))
    svg.box(328, 422, 484, 64, "Backups", ["35 days (prune); erasure register re-applied"], "data", ("personal", "secret", "retention"))
    svg.box(328, 498, 484, 64, "Rights", ["download, correct, erase, restrict, object (one month)"], "check")
    svg.zone(860, 60, 360, 520, "Recipients (by choice or setting)", "external")
    svg.box(878, 100, 324, 70, "School identity provider", ["issuer, subject, email, role"], "external")
    svg.box(878, 190, 324, 84, "Drive, OneDrive, GitHub", ["consent; own folder or repository;", "possibly USA (DPF, SCCs)"], "unverified", ("unverified",))
    svg.box(878, 294, 324, 84, "Cartridge Store", ["published games under a public handle;", "shared username by email (optional)"], "external")
    svg.box(878, 398, 324, 64, "SMTP provider", ["email address, sign-up link"], "external")
    svg.box(878, 482, 324, 64, "Hosting provider (processor)", ["everything on the server; EU/EEA"], "external")
    svg.arrow([(262, 135), (328, 132)])
    for y in (242, 349, 449):
        svg.arrow([(262, y), (328, 217)])
    svg.arrow([(812, 217), (878, 135)], "sign-in", both=True)
    svg.arrow([(812, 230), (878, 232)], "copies")
    svg.arrow([(812, 245), (878, 336)], "publish")
    svg.arrow([(812, 200), (878, 430)], "email")
    legend(svg, 24, 606)
    return svg


def game_loop() -> Svg:
    desc = ("The firmware owns the loop; a cartridge provides game_init, game_update and game_draw. Init runs once and "
            "sets the state S(0). Every frame (33 ms, about 30 per second) update reads the buttons u(t) and computes "
            "S(t+1) = update(S(t), u(t)); draw paints the 320 x 200 RGB565 framebuffer from S(t+1); the firmware "
            "presents it and waits for the next frame. Audio calls made during frame N take effect at N x 33 ms "
            "(the frame clock).")
    svg = Svg(960, 500, "The PRG32 game loop", desc)
    svg.text(480, 36, "The game loop: a discrete-time system", size=22, anchor="middle", bold=True, color=INK)
    svg.text(480, 60, "The firmware owns the loop; a cartridge only provides three functions.", anchor="middle")
    svg.box(40, 110, 220, 80, "game_init()", ["runs once: state S(0)"], "browser")
    svg.box(360, 110, 240, 80, "game_update()", ["every frame: S(t+1) =", "update(S(t), u(t))"], "server")
    svg.box(360, 260, 240, 80, "game_draw()", ["every frame: image(t) =", "draw(S(t+1)), painter's order"], "server")
    svg.box(700, 110, 220, 80, "input u(t)", ["prg32_input_read()", "button bit mask"], "plain")
    svg.box(700, 260, 220, 80, "320 x 200 screen", ["RGB565 framebuffer"], "plain")
    svg.box(40, 260, 220, 80, "present, wait", ["next frame at +33 ms"], "plain")
    svg.box(240, 390, 480, 64, "Audio: the frame clock", ["calls in frame N take effect at N x 33 ms; 20 ms buffers"], "data")
    svg.arrow([(260, 150), (360, 150)])
    svg.arrow([(700, 150), (600, 150)])
    svg.arrow([(480, 190), (480, 260)])
    svg.arrow([(600, 300), (700, 300)])
    svg.arrow([(360, 300), (260, 300)])
    svg.arrow([(150, 260), (150, 230), (420, 230), (420, 190)], "next frame", label_at=(285, 224))
    svg.text(480, 480, "About 30 frames per second: a 33 ms budget for update + draw on a 160 MHz RISC-V core.", anchor="middle")
    return svg


DIAGRAMS = {"architecture.svg": architecture, "pipeline.svg": pipeline, "data_flow.svg": data_flow,
            "game_loop.svg": game_loop}


def main() -> int:
    check = "--check" in sys.argv[1:]
    stale = []
    for name, draw in DIAGRAMS.items():
        text = draw().render()
        path = FIGURES / name
        if check:
            if not path.is_file() or path.read_text(encoding="utf-8") != text:
                stale.append(name)
        else:
            path.write_text(text, encoding="utf-8")
            print(f"Wrote docs/figures/{name}")
    if stale:
        print("out of date (run python3 tools/build_diagrams.py): " + ", ".join(stale), file=sys.stderr)
        return 1
    if check:
        print("diagrams are up to date")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
