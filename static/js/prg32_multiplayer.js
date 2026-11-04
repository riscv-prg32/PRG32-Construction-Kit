// Multiplayer on this computer: windows of this browser that play the same room see each other.
//
// On a console, prg32_multiplayer_join and the other multiplayer calls talk to the PRG32
// Multiplayer Server over Wi-Fi. In the browser the kit carries the same numbers between the
// windows (and tabs) of this browser with a BroadcastChannel: two windows side by side, each
// with its own keyboard focus or game controller, are two players. Nothing goes over the
// network and nothing is stored. See docs/multiplayer.md and docs/adr/0031.
//
// One message per frame and player, while it is in a room:
//   { kind: 'state', room, id, x, y, look, flags, input, frame }
// and { kind: 'leave', room, id } when it leaves (or the window closes).
// A player not heard from for 3 seconds is gone, as on the console (PRG32_MULTIPLAYER_PEER_TIMEOUT_MS).
window.PRG32Multiplayer = (function () {
  'use strict';

  const CHANNEL = 'prg32-kit-multiplayer-1';
  const TIMEOUT_MS = 3000;
  const MAX_PEERS = 8;                 // PRG32_MP_MAX_PEERS
  const ROOM = /^[A-Za-z0-9_.:-]{1,47}$/;

  const now = () => (typeof performance !== 'undefined' ? performance.now() : Date.now());
  const int = (value, low, high) => Math.max(low, Math.min(high, Math.trunc(Number(value) || 0)));

  // A player ID for this window: random, not 0, below 2^31 so it is a positive int in C too.
  function newPlayerId() {
    const buffer = new Uint32Array(1);
    if (typeof crypto !== 'undefined' && crypto.getRandomValues) crypto.getRandomValues(buffer);
    else buffer[0] = Math.floor(Math.random() * 0x7fffffff);
    return (buffer[0] & 0x7fffffff) || 1;
  }

  class Link {
    constructor(options = {}) {
      this.id = options.id || newPlayerId();
      this.room = '';
      this.others = new Map();        // id -> { state, seen }
      this.channel = null;
      const Channel = options.Channel || (typeof BroadcastChannel !== 'undefined' ? BroadcastChannel : null);
      if (Channel) {
        try {
          this.channel = new Channel(CHANNEL);
          this.channel.onmessage = event => this.receive(event.data);
        } catch (error) {
          this.channel = null;        // a page where it is not allowed plays alone
        }
      }
      if (typeof window !== 'undefined' && window.addEventListener) {
        window.addEventListener('pagehide', () => this.leave());
      }
    }

    get available() { return Boolean(this.channel); }

    post(message) {
      if (!this.channel) return;
      try { this.channel.postMessage(message); } catch (error) { /* closed */ }
    }

    // Enter a room ('' or an invalid name leaves). As on the console, joining forgets the others.
    join(room) {
      const name = ROOM.test(String(room || '')) ? String(room) : '';
      if (name === this.room) return;
      this.leave();
      this.room = name;
    }

    leave() {
      if (this.room) this.post({ kind: 'leave', room: this.room, id: this.id });
      this.room = '';
      this.others.clear();
    }

    // Tell the others in the room what this player shares (once per frame).
    send(state) {
      if (!this.room) return;
      this.post({
        kind: 'state', room: this.room, id: this.id,
        x: int(state.x, -32768, 32767), y: int(state.y, -32768, 32767),
        look: int(state.look, 0, 65535), flags: int(state.flags, 0, 65535),
        input: int(state.input, 0, 0x7ff), frame: int(state.frame, 0, 0xffffffff)
      });
    }

    receive(message) {
      if (!message || message.room !== this.room || !this.room) return;
      const id = Number(message.id) >>> 0;
      if (!id || id === this.id) return;
      if (message.kind === 'leave') { this.others.delete(id); return; }
      if (message.kind !== 'state') return;
      if (!this.others.has(id) && this.others.size >= MAX_PEERS) return;
      this.others.set(id, { state: message, seen: now() });
    }

    // The other players in the room, oldest ID first, so the order does not change from frame to frame.
    peers() {
      const time = now();
      for (const [id, other] of this.others) if (time - other.seen > TIMEOUT_MS) this.others.delete(id);
      return Array.from(this.others.entries())
        .sort((a, b) => a[0] - b[0])
        .map(([id, other]) => ({
          id, x: other.state.x | 0, y: other.state.y | 0, look: other.state.look | 0,
          flags: other.state.flags | 0, input: other.state.input | 0, frame: other.state.frame >>> 0
        }));
    }
  }

  // The WebAssembly core (prg32_runtime.js): give it the others before a frame, share after it.
  function beforeFrame(link, core) {
    if (!link || !core || !core._prg32_mp_clear_peers) return;
    core._prg32_mp_clear_peers();
    link.peers().forEach(peer => core._prg32_mp_put_peer(peer.id, peer.x, peer.y, peer.look, peer.flags, peer.input, peer.frame));
  }

  function afterFrame(link, core) {
    if (!link || !core || !core._prg32_mp_room) return;
    link.join(core.UTF8ToString(core._prg32_mp_room()));
    if (link.room) link.send(JSON.parse(core.UTF8ToString(core._prg32_mp_local_json())));
  }

  return { Link, beforeFrame, afterFrame, newPlayerId, TIMEOUT_MS };
})();
