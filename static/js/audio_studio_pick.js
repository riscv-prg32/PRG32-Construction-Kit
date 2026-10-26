// The Sprite Lab and AudioStudio menu items (templates/audio_studio_pick.html): list the student's
// projects and open the tool in the chosen one's IDE. The last project opened in the editor, the IDE or
// AudioStudio is offered first (localStorage prg32-kit-last-project, see /privacy#storage).
$(function () {
  const LAST = 'prg32-kit-last-project';
  let last = null;
  try { last = localStorage.getItem(LAST); } catch (_) { /* private window */ }

  // Sprite Lab or AudioStudio: both open as a tab of the project's IDE.
  const tab = { sprites: 'sprites', backgrounds: 'backgrounds' }[$('#toolPicker').data('tool')] || 'sound';
  function studioUrl(id) { return '/ide/' + encodeURIComponent(id) + '#' + tab; }

  Kit.api('/api/projects').then(data => {
    const projects = data.projects || [];
    const list = $('#audioProjects').empty();
    $('#audioPickStatus').text(projects.length ? tr('js.audio_studio_pick.choose_a_project', 'Choose a project:') : tr('js.audio_studio_pick.you_have_no_projects_yet', 'You have no projects yet.'));
    projects.forEach(project => {
      const item = $('<a class="list-group-item list-group-item-action d-flex align-items-center gap-2"></a>')
        .attr('href', studioUrl(project.id));
      item.append($('<i class="bi bi-music-note-list" aria-hidden="true"></i>'));
      item.append($('<span class="flex-grow-1"></span>').text(project.title || tr('js.audio_studio_pick.untitled', 'Untitled')));
      item.append($('<small class="text-muted"></small>').text(Kit.when(project.updated_at)));
      list.append(item);
      if (project.id === last) {
        $('#audioContinueTitle').text(project.title || tr('js.audio_studio_pick.untitled', 'Untitled'));
        $('#audioContinueOpen').attr('href', studioUrl(project.id));
        $('#audioContinue').prop('hidden', false);
      }
    });
  }).catch(error => {
    $('#audioPickStatus').text(tr('js.audio_studio_pick.could_not_load_your_projects', 'Could not load your projects: {message}', { message: error.message }));
  });
});
