-- DICOM Series Indexer / DuckDB-Wasm. All records and checkpoints stay local.
CREATE TABLE IF NOT EXISTS collections (
  id VARCHAR PRIMARY KEY,
  name VARCHAR NOT NULL,
  root_name VARCHAR NOT NULL,
  status VARCHAR NOT NULL DEFAULT 'New',
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  finished_at TIMESTAMP,
  discovered_count BIGINT DEFAULT 0,
  processed_count BIGINT DEFAULT 0,
  elapsed_active_ms DOUBLE DEFAULT 0,
  ignore_dicom_patient_id BOOLEAN DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS scan_units (
  collection_id VARCHAR NOT NULL,
  unit_key VARCHAR NOT NULL,
  fingerprint VARCHAR,
  completed BOOLEAN NOT NULL DEFAULT FALSE,
  PRIMARY KEY (collection_id, unit_key)
);

CREATE TABLE IF NOT EXISTS dicom_files (
  collection_id VARCHAR NOT NULL,
  unit_key VARCHAR NOT NULL,
  file_key VARCHAR NOT NULL,
  source_path VARCHAR,
  source_archive VARCHAR,
  series_folder_path VARCHAR,
  source_fingerprint VARCHAR,
  source_kind VARCHAR,
  dicom_patient_id VARCHAR,
  folder_patient_id VARCHAR,
  patient_id_resolved VARCHAR,
  patient_id_source VARCHAR,
  followup_label VARCHAR,
  study_uid VARCHAR,
  study_id VARCHAR,
  study_date VARCHAR,
  study_time VARCHAR,
  series_uid VARCHAR,
  series_number VARCHAR,
  sop_uid VARCHAR,
  acquisition_datetime VARCHAR,
  acq_ms BIGINT,
  bolus_start VARCHAR,
  series_description VARCHAR,
  protocol_name VARCHAR,
  modality VARCHAR,
  image_type VARCHAR,
  slice_thickness_mm VARCHAR,
  spacing_mm VARCHAR,
  orientation VARCHAR,
  image_position VARCHAR,
  rows INTEGER,
  columns INTEGER,
  pixel_spacing_mm VARCHAR,
  number_of_frames INTEGER,
  contrast_agent VARCHAR,
  scan_type VARCHAR,
  scan_type_evidence VARCHAR,
  estimated_phase VARCHAR,
  phase_confidence VARCHAR,
  phase_evidence VARCHAR,
  status VARCHAR,
  error_message VARCHAR,
  warnings VARCHAR,
  PRIMARY KEY(collection_id, file_key)
);

-- A physical occurrence is always retained; no source path is discarded
-- because its SOPInstanceUID was seen in another folder or ZIP.
CREATE OR REPLACE VIEW duplicate_sources AS
SELECT collection_id, sop_uid AS sop_instance_uid, COUNT(*) AS number_of_copies,
       STRING_AGG(source_path, ' | ' ORDER BY source_path) AS source_paths,
       STRING_AGG(DISTINCT series_folder_path, ' | ') AS source_folders,
       MIN(study_uid) AS example_study_uid, MIN(series_uid) AS example_series_uid
FROM dicom_files
WHERE status='ok' AND sop_uid <> ''
GROUP BY collection_id, sop_uid
HAVING COUNT(*) > 1;

-- Resolved IDs are computed from raw tag/folder IDs and the collection switch.
-- This view updates instantly when the switch changes, including old indexes.
CREATE OR REPLACE VIEW dicom_files_resolved AS
WITH archive_names AS (
  SELECT f.*,
    CASE WHEN f.source_kind='zip' THEN
      REGEXP_EXTRACT(COALESCE(f.source_archive,''),'([^/!]+)[.]zip$',1,'i')
    ELSE '' END AS accession_zip_basename,
    COALESCE(c.ignore_dicom_patient_id,TRUE) AS ignore_header_id
  FROM dicom_files f JOIN collections c ON c.id=f.collection_id
), candidates AS (
  SELECT a.*,
    NULLIF(TRIM(CASE WHEN accession_zip_basename <> '' THEN
      REGEXP_REPLACE(accession_zip_basename,'[ _-]+(?:pre|post)(?:[ _-]?[0-9]+)?$','','i')
    ELSE a.folder_patient_id END),'') AS usable_folder_patient_id,
    CASE WHEN accession_zip_basename <> '' THEN
      REGEXP_REPLACE(LOWER(REGEXP_EXTRACT(accession_zip_basename,
        '[ _-]+((?:pre|post)(?:[ _-]?[0-9]+)?)$',1,'i')),'[ _-]','','g')
    ELSE a.followup_label END AS resolved_followup_label,
    CASE WHEN LOWER(TRIM(a.dicom_patient_id)) IN
         ('anonymous','anonymized','anonymised','anon','unknown','n/a','none','null')
         OR REGEXP_MATCHES(LOWER(TRIM(a.dicom_patient_id)),'^x{2,}$')
      THEN NULL ELSE NULLIF(TRIM(a.dicom_patient_id),'') END AS usable_dicom_patient_id
  FROM archive_names a
), resolved AS (
  SELECT * EXCLUDE (folder_patient_id,followup_label,patient_id_resolved,patient_id_source,
                    accession_zip_basename,usable_folder_patient_id,resolved_followup_label,
                    usable_dicom_patient_id,ignore_header_id),
    COALESCE(usable_folder_patient_id,'') AS folder_patient_id,
    COALESCE(resolved_followup_label,'') AS followup_label,
    CASE WHEN ignore_header_id THEN
       COALESCE(usable_folder_patient_id,usable_dicom_patient_id,'')
       ELSE COALESCE(usable_dicom_patient_id,usable_folder_patient_id,'')
    END AS patient_id_resolved,
    CASE WHEN ignore_header_id AND usable_folder_patient_id IS NOT NULL THEN 'folder'
         WHEN ignore_header_id AND usable_dicom_patient_id IS NOT NULL THEN 'dicom_fallback'
         WHEN NOT ignore_header_id AND usable_dicom_patient_id IS NOT NULL THEN 'dicom'
         WHEN NOT ignore_header_id AND usable_folder_patient_id IS NOT NULL THEN 'folder_fallback'
         ELSE 'unavailable' END AS patient_id_source
  FROM candidates
)
SELECT * FROM resolved;

CREATE OR REPLACE VIEW dicom_instances AS
SELECT r.*,
       ROW_NUMBER() OVER (
         PARTITION BY collection_id,
           CASE WHEN sop_uid <> '' THEN 'sop:' || sop_uid ELSE 'file:' || file_key END
         ORDER BY file_key
       ) AS sop_occurrence
FROM dicom_files_resolved r
WHERE status='ok';

-- Predominant scan type/orientation are calculated from unique instances.
-- Secondary images in the same DICOM series remain counted and queryable.
CREATE OR REPLACE VIEW dicom_series AS
WITH unique_images AS (
  SELECT * FROM dicom_instances WHERE sop_occurrence=1
), grouped AS (
  SELECT collection_id, study_uid AS study_instance_uid,
    series_uid AS series_instance_uid,
    MODE(patient_id_resolved) FILTER (WHERE patient_id_resolved <> '') AS patient_id_resolved,
    MODE(dicom_patient_id) FILTER (WHERE dicom_patient_id <> '') AS dicom_patient_id,
    MODE(folder_patient_id) FILTER (WHERE folder_patient_id <> '') AS folder_patient_id,
    MODE(patient_id_source) AS patient_id_source,
    MODE(followup_label) FILTER (WHERE followup_label <> '') AS followup_label,
    MODE(study_id) FILTER (WHERE study_id <> '') AS study_id,
    MIN(study_date) AS study_date, MIN(study_time) AS study_time,
    MODE(series_number) FILTER (WHERE series_number <> '') AS series_number,
    MODE(series_description) FILTER (WHERE series_description <> '') AS series_description,
    MODE(protocol_name) FILTER (WHERE protocol_name <> '') AS protocol_name,
    MODE(modality) AS modality,
    MODE(slice_thickness_mm) FILTER (WHERE slice_thickness_mm <> '') AS slice_thickness_mm,
    MODE(spacing_mm) FILTER (WHERE spacing_mm <> '') AS slice_spacing_mm,
    MODE(orientation) FILTER (WHERE orientation <> 'unknown') AS orientation,
    MODE(rows) AS rows, MODE(columns) AS columns,
    MODE(pixel_spacing_mm) FILTER (WHERE pixel_spacing_mm <> '') AS pixel_spacing_mm,
    MODE(scan_type) AS predominant_scan_type,
    STRING_AGG(DISTINCT scan_type, '; ') AS scan_types_present,
    COUNT(DISTINCT scan_type) AS number_of_scan_types,
    COUNT(DISTINCT orientation) FILTER (WHERE orientation <> 'unknown') AS number_of_orientations,
    COUNT(DISTINCT slice_thickness_mm) FILTER (WHERE slice_thickness_mm <> '') AS number_of_thicknesses,
    COUNT(DISTINCT CONCAT(rows,'x',columns)) AS number_of_dimensions,
    COUNT(*) AS number_of_instances,
    SUM(number_of_frames) AS number_of_frames,
    COUNT(*) FILTER (WHERE scan_type='ct_axial') AS number_of_axial_ct_instances,
    SUM(number_of_frames) FILTER (WHERE scan_type='ct_axial') AS number_of_axial_ct_frames,
    COUNT(*) FILTER (WHERE scan_type='ct_coronal') AS number_of_coronal_ct_instances,
    COUNT(*) FILTER (WHERE scan_type='ct_sagittal') AS number_of_sagittal_ct_instances,
    COUNT(*) FILTER (WHERE scan_type='derived_ct') AS number_of_derived_ct_instances,
    COUNT(*) FILTER (WHERE scan_type='mpr') AS number_of_mpr_instances,
    COUNT(*) FILTER (WHERE scan_type='locator') AS number_of_locator_instances,
    COUNT(*) FILTER (WHERE scan_type='topogram') AS number_of_topogram_instances,
    COUNT(*) FILTER (WHERE scan_type='scout') AS number_of_scout_instances,
    STRING_AGG(DISTINCT series_folder_path, ' | ') AS series_folder_path,
    STRING_AGG(DISTINCT NULLIF(source_archive,''), ' | ') AS source_archive,
    MODE(contrast_agent) FILTER (WHERE contrast_agent <> '') AS contrast_agent,
    MODE(bolus_start) FILTER (WHERE bolus_start <> '') AS contrast_bolus_start_time,
    MIN(acquisition_datetime) FILTER (WHERE acquisition_datetime <> '') AS acquisition_datetime,
    MAX(acquisition_datetime) FILTER (WHERE acquisition_datetime <> '') AS acquisition_datetime_end,
    AVG(acq_ms) AS mean_acquisition_ms,
    COUNT(acq_ms) AS acquisition_times_count,
    MODE(estimated_phase) FILTER (WHERE estimated_phase <> 'unknown') AS known_phase,
    COUNT(DISTINCT estimated_phase) FILTER (WHERE estimated_phase <> 'unknown') AS known_phase_count,
    MODE(phase_confidence) FILTER (WHERE estimated_phase <> 'unknown') AS phase_confidence,
    MODE(phase_evidence) FILTER (WHERE estimated_phase <> 'unknown') AS phase_evidence,
    COUNT(DISTINCT patient_id_resolved) FILTER (WHERE patient_id_resolved <> '') AS patient_id_variants,
    COUNT(*) FILTER (WHERE dicom_patient_id <> '' AND folder_patient_id <> ''
                        AND dicom_patient_id <> folder_patient_id) AS patient_id_conflict_instances
  FROM unique_images
  GROUP BY collection_id,study_uid,series_uid
), timed AS (
  SELECT g.*,
    TRY_CAST(SPLIT_PART(contrast_bolus_start_time,':',1) AS DOUBLE) * 3600 +
    TRY_CAST(SPLIT_PART(contrast_bolus_start_time,':',2) AS DOUBLE) * 60 +
    TRY_CAST(SPLIT_PART(contrast_bolus_start_time,':',3) AS DOUBLE) AS bolus_seconds,
    MOD(mean_acquisition_ms,86400000.0)/1000.0 AS mean_acquisition_seconds
  FROM grouped g
)
SELECT collection_id, study_instance_uid,series_instance_uid,
  patient_id_resolved AS patient_id, dicom_patient_id,folder_patient_id,
  patient_id_resolved,patient_id_source,followup_label,study_id,study_date,study_time,
  series_number,series_description,protocol_name,modality,slice_thickness_mm,
  slice_spacing_mm,orientation,rows,columns,pixel_spacing_mm,
  predominant_scan_type AS scan_type,scan_types_present,number_of_scan_types,
  CASE WHEN predominant_scan_type='ct_axial'
     AND COALESCE(number_of_axial_ct_frames,0)>=20 THEN 'yes' ELSE 'no' END AS axial_ct_candidate,
  number_of_instances,number_of_frames,number_of_axial_ct_instances,number_of_coronal_ct_instances,
  number_of_sagittal_ct_instances,number_of_derived_ct_instances,number_of_mpr_instances,
  number_of_locator_instances,number_of_topogram_instances,number_of_scout_instances,
  series_folder_path,source_archive,contrast_agent,contrast_bolus_start_time,
  acquisition_datetime,acquisition_datetime_end,
  CASE WHEN mean_acquisition_ms IS NULL THEN NULL ELSE
    STRFTIME(CAST(TO_TIMESTAMP(mean_acquisition_ms/1000.0) AS TIMESTAMP),'%Y-%m-%d %H:%M:%S.%f')
  END AS mean_acquisition_datetime,
  acquisition_times_count,
  CASE WHEN mean_acquisition_seconds IS NULL OR bolus_seconds IS NULL THEN NULL
    WHEN MOD(mean_acquisition_seconds-bolus_seconds+86400,86400)<=900 THEN
      ROUND(MOD(mean_acquisition_seconds-bolus_seconds+86400,86400),1)
    ELSE NULL END AS postcontrast_delay_seconds,
  CASE WHEN modality <> 'CT' THEN 'unknown'
    WHEN known_phase_count>1 THEN 'mixed'
    ELSE COALESCE(known_phase,'unknown') END AS estimated_phase,
  COALESCE(phase_confidence,'unknown') AS phase_confidence,
  COALESCE(phase_evidence,'No reliable phase indicator') AS phase_evidence,
  number_of_orientations,number_of_thicknesses,number_of_dimensions,
  patient_id_variants,patient_id_conflict_instances
FROM timed;

CREATE OR REPLACE VIEW dicom_studies AS
SELECT collection_id,patient_id_resolved,study_instance_uid,MIN(study_date) AS study_date,
       COUNT(*) AS number_of_series,
       COUNT(*) FILTER (WHERE estimated_phase='portal_venous' AND axial_ct_candidate='yes') AS axial_venous_series
FROM dicom_series
GROUP BY collection_id,patient_id_resolved,study_instance_uid;
