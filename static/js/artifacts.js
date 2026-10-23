(function () {
  function row(artifact) {
    return `<tr>
      <td><div class="fw-semibold">${Kit.escape(artifact.name)}</div><div class="small text-muted">${Kit.escape(artifact.id)}</div></td>
      <td><span class="badge text-bg-secondary">${Kit.escape(artifact.kind)}</span></td>
      <td>${Kit.escape(artifact.content_type)}</td>
      <td class="small text-muted">${Kit.escape(Kit.when(artifact.updated_at))}</td>
      <td class="text-end">
        ${artifact.kind === 'prg32_cartridge' ? `<a class="btn btn-outline-success btn-sm" href="/player?artifact=${encodeURIComponent(artifact.id)}" title="${Kit.escape(tr('player.play_in_browser', 'Play in browser'))}"><i class="bi bi-play-fill"></i></a>` : ''}
        <a class="btn btn-outline-primary btn-sm" href="/api/artifacts/${encodeURIComponent(artifact.id)}/download"><i class="bi bi-download"></i></a>
        <button class="btn btn-outline-danger btn-sm delete-artifact" data-id="${Kit.escape(artifact.id)}"><i class="bi bi-trash"></i></button>
      </td>
    </tr>`;
  }

  function load() {
    return Kit.api('/api/artifacts').then(data => {
      $('#artifactRows').html(data.artifacts.map(row).join('') || `<tr><td colspan="5" class="text-center text-muted p-4">${tr('js.artifacts.no_artifacts_yet', 'No artifacts yet. Generate C, convert sprites, package a cartridge, or upload a file.')}</td></tr>`);
    });
  }

  $('#artifactRows').on('click', '.delete-artifact', function () {
    if (!confirm(tr('js.artifacts.delete_artifact', 'Delete artifact?'))) return;
    Kit.api('/api/artifacts/' + encodeURIComponent($(this).data('id')), { method: 'DELETE' })
      .then(() => { Kit.toast(tr('js.artifacts.artifact_deleted', 'Artifact deleted'), 'success'); load(); })
      .catch(err => Kit.toast(err.message, 'danger'));
  });

  $('#uploadArtifactForm').on('submit', function (event) {
    event.preventDefault();
    const form = new FormData(this);
    Kit.api('/api/artifacts/upload', { method: 'POST', body: form })
      .then(() => { Kit.toast(tr('js.artifacts.artifact_uploaded', 'Artifact uploaded'), 'success'); this.reset(); load(); })
      .catch(err => Kit.toast(err.message, 'danger'));
  });

  load().catch(err => Kit.toast(err.message, 'danger'));
})();
