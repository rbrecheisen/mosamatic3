# Batch L3 slice selection

Apply the contents of `payload/` to the Mosamatic3 project root. This patch adds
`core/management/commands/batch_slice_select.py` and its tests. It uses the
existing shared slice-select engine; it does not create web datasets or enqueue
Celery tasks. It runs synchronously in the container where the command is started.

## Docker setup (Windows example)

Choose a host directory containing the CT folders and a list file, for example
`M:\CT_scans`. Create an existing writable host directory for the results, for
example `M:\L3_results`. In the **web** service's `volumes:` section of
`docker-compose-dev.yml`, add these entries alongside the existing volumes:

```yaml
      - 'M:/CT_scans:/scan_input:ro'
      - 'M:/L3_results:/scan_output'
```

Rebuild/recreate the containers using your normal script. Docker Desktop must be
able to access the host drive. In `M:\CT_scans\scan_folders.txt`, use paths
**as seen inside the container**, one complete scan folder per line:

```text
# Lines starting with # and blank lines are ignored
/scan_input/PATIENT001/CT
/scan_input/PATIENT002/CT
```

A Windows path such as `M:\CT_scans\PATIENT001\CT` is not a valid path inside
the Linux container. If scan folders are spread across multiple host roots, mount
each root and use the corresponding container path in the list. Quotes around
a complete path are accepted. Relative paths are resolved relative to the list.

From the project directory, inspect the list without running TotalSegmentator:

```powershell
docker compose -f docker-compose-dev.yml exec web python manage.py batch_slice_select /scan_input/scan_folders.txt --output-dir /scan_output --dry-run
```

Then process sequentially:

```powershell
docker compose -f docker-compose-dev.yml exec web python manage.py batch_slice_select /scan_input/scan_folders.txt --output-dir /scan_output
```

Ctrl+C stops the command; rerun the same command to resume. It checks each
folder's source fingerprint (filenames, SOP UIDs, sizes and modification times)
and validates its saved DICOM and both PNGs before skipping it. Failed folders
are retried on the next run. `--overwrite` forces reprocessing completed folders.
Do not run two instances against the same output directory simultaneously.

Temporary files and TotalSegmentator masks can be large. The default temporary
directory is the container's default (usually `/tmp`). For another location, bind
mount a directory to the container and pass `--temp-dir /container/temp/path`.
The directory must already exist and be writable. TotalSegmentator's model weights
and compatible compute environment must be available to the web container.

## Outputs

- `selected/<folder-name>_<path-hash>.dcm`: original selected DICOM bytes.
- `axial/` and `sagittal/`: corresponding PNGs. Inspect sagittal images to verify
  that the intended vertebra and slice were selected.
- `records/`: per-folder JSON completion/error records used for resume.
- `batch_slice_select_report.csv`: current invocation's progress and outcomes;
  it is updated after each folder. Per-folder records persist across invocations.

The folder name is the name of the scan directory, which may be a generic name
such as `CT`; the path hash prevents collisions. The report maps it to its source.
It records the engine's vertebral midpoint as `selected_z_position_mm`; this is
not necessarily the exact selected DICOM slice's Z coordinate.

Only immediate files in each listed folder are inspected; no recursive discovery
is performed. Non-CT files are ignored. The command rejects folders with zero or
multiple CT series, missing series/SOP identifiers, duplicate SOP IDs or Z
positions, multiframe CT, missing positions, or fewer than two slices. Repeated
identical folder paths in the list are processed once. It does not deduplicate
series across different folders. It does not establish that CT coverage includes
L3, or validate geometry for unusual/oblique acquisitions; review outputs.
A folder error is recorded and processing continues; a nonzero exit status is
returned after processing all folders if any failed.

The existing shared engine runs TotalSegmentator in fast mode, uses its L3 mask,
selects the closest source DICOM, and makes axial and sagittal review images.
Masks are temporary and removed. Test first on a few known scans and compare the
selected slice and sagittal review with your existing web task. No real
TotalSegmentator or Docker test was performed when creating this patch.

Optional tests, from the project root in an installed environment:

```text
python -m unittest discover -s tests -p test_batch_slice_select.py -v
```
