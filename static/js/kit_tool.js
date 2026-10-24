// The sections of a tool in the IDE (AudioStudio: voices, sound effects, soundtracks, samples):
// a vertical tab list in the left column switches the list, the editor and the toolbar buttons
// that belong to one section (_audio_studio.html). Left/Right/Up/Down/Home/End move, as in any tab list.
(function () {
  'use strict';
  function show(tool, section) {
    tool.find('.kit-sections [data-section]').each(function () {
      const on = $(this).data('section') === section;
      $(this).toggleClass('active', on).attr({ 'aria-selected': String(on), tabindex: on ? '0' : '-1' });
    });
    tool.find('.kit-section-pane').each(function () { $(this).prop('hidden', $(this).data('section') !== section); });
    tool.find('.kit-section-only').each(function () { $(this).prop('hidden', $(this).data('section') !== section); });
    tool.attr('data-section', section);
  }
  $(document).on('click', '.kit-sections [data-section]', function () {
    show($(this).closest('.kit-tool'), $(this).data('section'));
  });
  $(document).on('keydown', '.kit-sections [data-section]', function (event) {
    const tabs = $(this).closest('.kit-sections').find('[data-section]');
    const index = tabs.index(this);
    const next = { ArrowDown: index + 1, ArrowRight: index + 1, ArrowUp: index - 1, ArrowLeft: index - 1,
      Home: 0, End: tabs.length - 1 }[event.key];
    if (next === undefined) return;
    event.preventDefault();
    const target = tabs.eq((next + tabs.length) % tabs.length);
    show($(this).closest('.kit-tool'), target.data('section'));
    target.trigger('focus');
  });
  window.PRG32KitTool = { show: (tool, section) => show($(tool), section) };
  $('.kit-tool').each(function () {
    const first = $(this).find('.kit-sections [data-section]').first();
    if (first.length) show($(this), first.data('section'));
  });
})();
