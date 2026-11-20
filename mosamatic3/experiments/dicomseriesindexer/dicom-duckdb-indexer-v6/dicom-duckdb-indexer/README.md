# DICOM Series Indexer — DuckDB edition (offline)

**Revision 1.3 (2026-11-20):** Supports two verified layouts: (1) root/patient folder/nested scan folders, and (2) root/one-patient ZIP archives. For each ZIP, `folder_patient_id` is derived from the ZIP filename without `.zip`, stripping `-pre`/`-postN` into `followup_label`. The ZIP's internal scan folder names are not treated as patient IDs. This works for newly indexed files and retroactively in the DuckDB query views for old indexed ZIP files (no reindex needed). The **Ignore PatientID in DICOM header** checkbox stays checked by default. No ZIP-in-ZIP extraction or staging is implemented.

**How to verify your update:** the top heading must say **v1.3**, and the **Ignore PatientID in DICOM header** checkbox must appear below the indexing buttons. If either is absent, you are running an old installation, regardless of hard refresh. Do not extract this ZIP into an existing `dicom-duckdb-indexer` directory (which can create `dicom-duckdb-indexer/dicom-duckdb-indexer`). Extract it in a *fresh, empty parent folder* and run the launcher within its single `dicom-duckdb-indexer` subfolder. Stop other servers listening on port `8765` first. Using the same `http://localhost:8765` origin preserves your existing browser database.

A browser-local DICOM inventory tool for accession ZIP archives and nested patient-folder trees. It stores metadata, scan status, and resume checkpoints **only in DuckDB-Wasm using the browser's OPFS**. There is no IndexedDB index, server-side database, upload, or external API call.

## Run

1. Extract the **entire ZIP** into a folder. Keep `index.html`, `app.js`, `schema.sql`, `parser-core.js`, `scanner-worker.js`, and `assets/` together.
2. Install Python 3 if necessary (no Python packages required).
3. On Windows double-click `start-windows.bat`. On macOS/Linux run `sh start-macos-linux.sh`.
4. In Chrome or Edge, open **http://localhost:8765**. Use this **exact URL** every time: browser storage belongs to the specific origin (scheme + hostname + port). Opening `index.html` directly with `file://` will not work.
5. Enter a collection name, click **Create collection** and select the dataset root. On future visits select the collection and click **Choose root folder & start / resume**, selecting that same root again. The **Ignore PatientID in DICOM header** checkbox defaults to checked, and its choice is remembered per collection. It is disabled while scanning.
6. Use the example SQL queries or write your own. Click **Run SQL** to browse results in 200-row pages. Click headers to sort across all matching rows; drag headers to move columns or their right edge to resize. Tick the first-column checkboxes to select individual rows, including across different pages. **Export selected rows to CSV** exports exactly those checked rows; **Export full query CSV** exports every matching row. Use **Back up database** regularly to keep a transferable `.duckdb` database file.

## How resume works

- Each database batch of at most 250 candidate files commits atomically. Each completed ZIP or folder of loose DICOM files is checkpointed in DuckDB (including folders nested several levels deep). A stopped job, crashed tab or browser restart retains the committed work.
- The selected root **must be reselected** after closing the page; browser directory handles are not persisted. The tool skips completed ZIPs/folders during processing, but it still traverses their names and re-counts ZIP directory entries in the initial discovery pass.
- **Pause** waits for the current parsed image / batch boundary, **Resume** continues, **Stop** flushes and closes the job. Browser close or OS power loss may lose only the uncommitted batch. Do not leave a tab paused indefinitely if you need to reclaim its RAM.
- A changed ZIP fingerprint is detected. In-place edits within already completed unpacked scan folders are **not** detected; make a new collection after changing underlying source files. If an incomplete scan folder changes, previously committed file records are still skipped.

## SQL schema

- `collections`: named inventory and performance metrics.
- `scan_units`: resumable top-level folders / ZIP units.
- `dicom_files`: **every source occurrence**, including parsing errors and repeated SOP Instance UIDs, with precise `source_path`; source paths within a ZIP use `archive.zip!/entry/path.dcm`.
- `dicom_files_resolved`: the same source occurrences with dynamically resolved `patient_id_resolved` and `patient_id_source` according to the collection checkbox. Prefer this view when querying file-level patient IDs: the raw `dicom_files.patient_id_resolved` column is the historical value saved during indexing and does not change when the checkbox changes.
- `dicom_instances`: physical images plus `sop_occurrence` (1 for the first occurrence).
- `dicom_series`: **one row per unique study/series**, based on unique SOP UIDs, with predominant orientation and scan type; secondary type counts and evidence retained. All MPR, scout, locator and topogram images remain in the database.
- `duplicate_sources`: number of physical occurrences and all their source paths for repeated SOP Instance UIDs.
- `dicom_studies`: one row per study and resolved patient.

Use `SELECT * FROM dicom_series LIMIT 10` to inspect every column. **Acquisition mean** is calculated across slices with valid timestamps. `postcontrast_delay_seconds` is the mean acquisition time minus DICOM ContrastBolusStartTime (`0018,1042`), adjusted for midnight; a delay outside 0–900 seconds returns `NULL`. Missing or contradictory timing data should be evaluated manually. The contrast phase is **heuristic**, inferred from folder names and DICOM descriptions; folder terms `blanco`, `native`, `noncontrast` and typical 20s/40s/60s delays are considered.

`number_of_instances` counts distinct DICOM images in a series, whereas `number_of_frames` is the total of their declared frame counts. In multi-frame enhanced CT they can differ greatly. Duplicate *source files* are not counted twice in either series total.

### Patient ID priority and ZIP folder names

The checkbox affects `dicom_files_resolved`, `dicom_instances`, `dicom_series` and `dicom_studies` immediately, even for existing databases. The raw `dicom_patient_id` and `folder_patient_id` columns remain unchanged. A blank or commonplace placeholder DICOM PatientID is treated as missing; otherwise it can be used as a fallback, exactly as requested.

For unpacked datasets, the patient ID is taken from the first folder immediately under the chosen root (e.g. `PAT123-post2/CT/...` → ID `PAT123`, follow-up `post2`). For one-patient ZIPs, the patient ID comes from the ZIP filename itself (e.g. `PAT456-post1.zip!/CT/venous/IM001.dcm` → ID `PAT456`, follow-up `post1`), never from its internal scan folders. This assumes the ZIP basename is precisely the patient ID plus an optional follow-up suffix. If the filename also contains an accession number, a format-specific extraction rule is needed. Multi-patient ZIP archives are **not supported** because identifying a patient from their first internal folder cannot safely be distinguished from arbitrary scan-type folders without a real example. ZIP-in-ZIP archives are **not supported**.

## Performance and constraints

- This is a **metadata parser**, not a DICOM pixel decoder. For a typical source it reads the header and stops before the pixel payload; ZIP entries may have to be decompressed until the header is reached. ZIP64 central directories are supported; multipart ZIPs, encrypted ZIPs, some unusual compression methods and some uncommon DICOM transfer syntaxes are not.
- Browser local storage is subject to quota / eviction. Request durable storage and download periodic `.duckdb` backups. Keep backups outside the browser profile.
- The embedded database handles millions of rows, but some views aggregate all instances and can be slow over millions of rows. Query `dicom_series` and export selected folder/archive paths; do not expect the browser to open image pixels for 1.5 TB.
- CSV exports use streaming to a user-chosen file when Chrome's File System Access API supports it; otherwise they fall back to an in-memory download, which is unsuitable for extremely large per-file exports.
- The results table pages through DuckDB without loading the full query result into memory. Sorting applies to the entire query result, not just the visible page. Only checked rows are retained in memory for selected-row export; they stay selected across pages, sorts and column rearrangements. **Changing the SQL query and running it clears selections**; repeating the same query retains them. Selected-row export uses the current visible column order.
- No raw pixel data is stored or exported. However patient metadata **is** identifiable health information; protect your browser profile and database backup files accordingly.
- For performance comparisons, `collections` has `processed_count`, `discovered_count`, and `elapsed_active_ms`. Active processing excludes explicit pauses but includes metadata discovery and DuckDB writes. `elapsed_active_ms` is persisted.

## Why a local web server?

Browser module and worker security restrictions block local `file://` access. The bundled Python server binds to `127.0.0.1` only and serves static files from this folder; it does not receive the chosen DICOM files. The browser's File System Access APIs read the selected folder directly.

## Components / licenses

- DuckDB-Wasm `1.32.0`, from `@duckdb/duckdb-wasm`: MIT License, https://github.com/duckdb/duckdb-wasm
- Apache Arrow JS (embedded by the JS bundling step): Apache-2.0, https://github.com/apache/arrow
- DICOM/ZIP metadata scanner and user interface in this distribution are standalone application code.

The engine is pinned to DuckDB-Wasm 1.32.0 because the DuckDB team's September 2026 OPFS advisory notes a persistence regression in a later development release. Updating DuckDB assets requires separate regression testing.
