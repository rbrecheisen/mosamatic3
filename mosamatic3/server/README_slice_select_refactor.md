# Slice Select shared-engine patch

Apply the contents of payload/ over the Mosamatic3 project root. This patch is
based on _sources(9).zip. No migrations or new dependencies are required.
Rebuild/restart the task worker using your usual Docker deployment procedure;
a restart alone does not update code baked into an existing Docker image.

## Changes

- core/processing/sliceselect/engine.py: reusable filesystem engine with explicit
  options and neutral in-memory artifacts. It imports no Django/Celery code.
- core/processing/sliceselect/service.py: web adapter; retains dataset discovery,
  task parameters, progress, cancellation, manifests, resume, output registration
  and output names. The L3/T4 selection algorithm and fast mode are unchanged.
- Each series is staged separately with hard links, falling back to copies.
  Both TotalSegmentator and sagittal QA see only that series. Temporary per-series
  files/masks are removed after success or failure.
- Patient path index 0 is respected (previously treated as 1).
- Sagittal QA line shows the actual selected DICOM Z, rather than the continuous
  vertebral midpoint. Manifest selected_z_position_mm retains the vertebral
  midpoint, as before.

No CLI/batch script is included yet. Web discovery still groups the existing
input dataset by SeriesInstanceUID; no new multiple-series policy is introduced.

## Web verification

1. Run Slice Select on a small known CT dataset with the same parameters used
   previously. Prefer a new input dataset so an unfinished task's existing
   completed-series records do not skip the scans you want to test.
2. Check selected DICOMs, axial PNGs, sagittal mask overlays/selection lines,
   sagittal_thumbnails.png, and slice_select_manifest.json.
3. Compare the selected SOPInstanceUID with the previous run. For a folder that
   originally contained multiple series, correcting isolation may change results.
4. Test cancellation between scans and rerun with identical parameters on the
   same input: completed scans should be skipped in the resumed output dataset.

## Validation performed

Seven standalone tests passed using synthetic DICOMs and a synthetic NIfTI
vertebral mask. They cover real nearest-slice selection, axial PNG rendering,
series staging, copy fallback, failure cleanup, patient naming, thumbnail layout,
web artifact conversion and resume checks. TotalSegmentator and sagittal rendering
were mocked; no real model inference or running Django/Celery web integration
was tested here. All retained web orchestration functions were also compared
against the original source structurally and are unchanged.

Optional test command from the project root in its installed environment:

    python -m unittest discover -s tests -p test_sliceselect_engine.py -v
