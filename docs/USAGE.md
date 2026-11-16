# Using Pauselith (technical executable: KiyoCut.exe)

1. **Añadir vídeos** or Ctrl+O imports recordings; dragging is also supported.
2. **Configurar** selects the voice track. Start with the approved profile.
3. **Elegir** selects output, or paste an existing absolute folder path and press Enter. Empty means beside each source. Invalid edits show an error, retain the previous saved preference and block processing.
4. **Procesar vídeos** or Ctrl+Enter starts. Queue progress means reviewed work, not that every export succeeded.
5. Select a result: **Terminado** is complete; **Entrega parcial** needs attention; **Error/Cancelado** do not advertise an unverified final video. Read warnings and **Abrir registro**. Metrics can scroll in constrained views; terminal warnings remain above the result buttons. The readonly result path supports selection/copy and a full-path tooltip when its text extends beyond the field.
6. **Abrir vídeo** opens an available principal; **Ver carpeta** opens outputs and reports.

Escape or **Cancelar cola** stops the current task; pending tasks remain available. Re-add a cancelled source to retry. Removing/clearing rows does not delete media. **Restaurar perfil aprobado** requires **Guardar**. Settings apply to future jobs.

Installed settings/jobs/logs: `%LOCALAPPDATA%\KiyoCut`. Portable: `data/` in the extracted package. Uninstall intentionally retains state and media. To remove retained state later, close the app and delete only that documented data directory; do not use it as your output destination if you intend to remove it.

Setup updates preserve external state. For a portable update, extract into a new folder and copy only the old `data/` after closing both copies. Legacy personal settings beside an old executable may be copied manually if desired; this release does not migrate or touch existing personal installations. Logs/job files can contain private local paths: redact before sharing.
