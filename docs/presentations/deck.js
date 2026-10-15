// Slide navigation for the PRG32-Construction-Kit tutorial decks.
// Keys: right/left arrows, Page Up/Down, space, Home, End, F for full screen.
(function () {
  const slides = Array.from(document.querySelectorAll('.slide'));
  const counter = document.querySelector('.deck-count');
  let current = 0;

  function fit() {
    const deck = document.querySelector('.deck');
    const scale = Math.min(deck.clientWidth / 1280, deck.clientHeight / 720) * 0.97;
    slides.forEach(slide => { slide.style.transform = `translate(-50%, -50%) scale(${scale})`; });
  }

  function show(index) {
    current = Math.max(0, Math.min(slides.length - 1, index));
    slides.forEach((slide, i) => slide.classList.toggle('active', i === current));
    if (counter) counter.textContent = `${current + 1} / ${slides.length}`;
    if (location.hash !== '#' + (current + 1)) history.replaceState(null, '', '#' + (current + 1));
  }

  document.addEventListener('keydown', event => {
    if (['ArrowRight', 'PageDown', ' '].includes(event.key)) { show(current + 1); event.preventDefault(); }
    if (['ArrowLeft', 'PageUp'].includes(event.key)) { show(current - 1); event.preventDefault(); }
    if (event.key === 'Home') show(0);
    if (event.key === 'End') show(slides.length - 1);
    if (event.key === 'f' || event.key === 'F') {
      if (document.fullscreenElement) document.exitFullscreen();
      else document.documentElement.requestFullscreen().catch(() => {});
    }
  });
  document.querySelectorAll('[data-go]').forEach(button => button.addEventListener('click', () => show(current + (button.dataset.go === 'next' ? 1 : -1))));
  let touchX = null;
  document.addEventListener('touchstart', event => { touchX = event.touches[0].clientX; });
  document.addEventListener('touchend', event => {
    if (touchX === null) return;
    const dx = event.changedTouches[0].clientX - touchX;
    if (Math.abs(dx) > 50) show(current + (dx < 0 ? 1 : -1));
    touchX = null;
  });
  window.addEventListener('resize', fit);
  window.addEventListener('hashchange', () => show(parseInt(location.hash.slice(1), 10) - 1 || 0));
  fit();
  show(parseInt(location.hash.slice(1), 10) - 1 || 0);
})();
