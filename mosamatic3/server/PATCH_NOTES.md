# Improved processing error reporting (patch)

- In Rescale and L3/T4 segmentation, invalid DICOM images stop the task with a descriptive filename, decoded shape, number of frames and samples per pixel. No silent skipping or subsequent misleading empty-output error.
- Calculate Scores checks DICOM shape and reports missing pixel spacing and unsupported segmentation dimensions.
- Worker logs include the summary and the full Python traceback.
- Standalone task runs persist an error message in `TaskRun.error_message`; the status API returns it and the Task page shows it live and in the last five runs. This requires the included Django migration.
- Pipeline failures store both step and pipeline error messages and display them on the Pipelines page, with expandable step details. Step setup errors are also captured.
- Pipeline-to-DICOM-import status synchronization is performed on failed steps.
- Task status API is now scoped to the logged-in task owner (was not scoped before).

Apply `payload/` into the project root and deploy/rebuild **both** the web and worker images. Run `python manage.py migrate` (or the equivalent inside the web container) before starting processing. For existing failures, only pipeline history that already stored details can be displayed; past task failures are not retroactively reconstructed.

Note: 3D/multiframe images are *rejected*, not automatically converted. This intentionally avoids silently selecting the wrong frame. Slice selection also logs per-scan failures and includes the first failure reason in its status message; full errors remain in its manifest.
