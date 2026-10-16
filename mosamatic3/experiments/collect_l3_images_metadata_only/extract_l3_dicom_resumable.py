#!/usr/bin/env python3
"""Resumable metadata-only collection of unique CT L3 candidates.

Usage:
  pip install pydicom
  python extract_l3_dicom_resumable.py project_folders.txt D:\\L3_output

All valid CT images in supplied folders are assumed to be preselected L3 images.
Copies original DICOM bytes unchanged. SOPInstanceUID deduplicates globally across
all drives/projects; if missing, SHA-256 of the complete file is used.

Persistent SQLite registry: output/l3_registry.sqlite3
Exports: output/images.csv (one row per unique image)
         output/image_sources.csv (all encountered source paths)
         output/scan_errors.csv

Resume behavior: files with matching (path, size, mtime_ns) are skipped without
reading the DICOM again. Changed sources are reprocessed. Interrupted copies are
reconciled. Files already in the output folder are indexed on first use, with
original names retained (new copies use L3_00001.dcm, etc.).

For clinical research: original DICOM files and exported metadata may identify
patients. Process only in an approved secure environment.
"""
import argparse
import csv
import hashlib
import json
import os
import re
import sqlite3
import sys
from pathlib import Path

import pydicom

METADATA = [
    'Modality','BodyPartExamined','StudyDescription','SeriesDescription','ProtocolName',
    'InstitutionName','InstitutionAddress','InstitutionalDepartmentName',
    'Manufacturer','ManufacturerModelName','StationName','SoftwareVersions',
    'KVP','XRayTubeCurrent','Exposure','ExposureTime','ConvolutionKernel',
    'SliceThickness','SpacingBetweenSlices','PixelSpacing','ReconstructionDiameter',
    'ConvolutionKernelGroup','RescaleSlope','RescaleIntercept',
    'ContrastBolusAgent','ContrastBolusRoute','ContrastBolusVolume','ContrastBolusStartTime',
    'ImageType','Rows','Columns','StudyDate','AcquisitionDate','AcquisitionTime',
    'PatientSex','PatientAge','PatientSize','PatientWeight','PatientPosition',
    'ImagePositionPatient','ImageOrientationPatient','SliceLocation',
    'SeriesNumber','InstanceNumber','StudyID','FrameOfReferenceUID',
    'StudyInstanceUID','SeriesInstanceUID','SOPInstanceUID',
]
COUNTRY_PATTERNS = {
    'NL':r'\b(?:netherlands|nederland|holland)\b',
    'BE':r'\b(?:belgium|belgie|belgië|belgique)\b',
    'DE':r'\b(?:germany|deutschland)\b',
    'GB':r'\b(?:united kingdom|england|scotland|wales)\b',
    'FR':r'\bfrance\b', 'US':r'\b(?:united states|usa)\b',
    'IT':r'\b(?:italy|italia)\b', 'ES':r'\b(?:spain|españa|espana)\b',
    'CH':r'\b(?:switzerland|schweiz|suisse)\b',
    'AT':r'\b(?:austria|österreich|oesterreich)\b',
    'DK':r'\b(?:denmark|danmark)\b', 'SE':r'\b(?:sweden|sverige)\b',
    'NO':r'\b(?:norway|norge)\b', 'FI':r'\b(?:finland|suomi)\b',
    'PL':r'\b(?:poland|polska)\b', 'CA':r'\bcanada\b',
    'AU':r'\baustralia\b',
}
# Add institution-name overrides after manually validating site names:
HOSPITAL_COUNTRY = {}


def get_value(ds, keyword):
    v = getattr(ds, keyword, None)
    if v is None:
        return ''
    if isinstance(v, (list, tuple)) or type(v).__name__ == 'MultiValue':
        return '|'.join(str(x) for x in v)
    return str(v).replace('\r',' ').replace('\n',' ').strip()


def country_info(meta):
    h = meta.get('InstitutionName','').strip().casefold()
    if h in HOSPITAL_COUNTRY:
        return HOSPITAL_COUNTRY[h], 'hospital mapping'
    a = meta.get('InstitutionAddress','')
    matches = [code for code, pattern in COUNTRY_PATTERNS.items()
               if re.search(pattern, a, flags=re.IGNORECASE)]
    return (matches[0], 'institution address') if len(matches) == 1 else ('', '')


def project_info(root):
    # Match named projects even when source_root is a nested subfolder.
    m = re.search(r'(P\d{4})_([^\\/]+)', str(root), re.IGNORECASE)
    if m:
        return m.group(1).upper(), m.group(2).strip()
    return '', root.name


def sha256(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def dedup_key(ds, path):
    uid = get_value(ds, 'SOPInstanceUID')
    return 'UID:' + uid if uid else 'SHA256:' + sha256(path)


def resolve_roots(location):
    location = location.expanduser().resolve()
    if location.is_dir():
        return [location]
    if not location.is_file():
        raise ValueError('Not a directory or project folder list: ' + str(location))
    if location.suffix.lower() != '.txt':
        raise ValueError('Expected .txt folder list: ' + str(location))
    roots = []
    for n, raw in enumerate(location.read_text(encoding='utf-8-sig').splitlines(), 1):
        line = raw.strip().strip('"').strip("'")
        if not line or line.startswith('#'):
            continue
        p = Path(line).expanduser()
        if not p.is_absolute():
            p = location.parent / p
        p = p.resolve()
        if not p.is_dir():
            raise ValueError(f'Project folder list line {n}: missing directory {p}')
        if p not in roots:
            roots.append(p)
    if not roots:
        raise ValueError('No project directories listed')
    return roots


def open_db(path):
    db = sqlite3.connect(path)
    db.execute('PRAGMA busy_timeout=10000')
    db.execute('PRAGMA journal_mode=WAL')
    db.execute('PRAGMA foreign_keys=ON')
    db.executescript('''
        CREATE TABLE IF NOT EXISTS images (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            dedup_key TEXT NOT NULL UNIQUE,
            output_filename TEXT UNIQUE,
            status TEXT NOT NULL CHECK(status IN ('PENDING','COMPLETE')),
            byte_size INTEGER,
            meta_json TEXT NOT NULL DEFAULT '{}',
            country TEXT NOT NULL DEFAULT '',
            country_basis TEXT NOT NULL DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS sources (
            source_path TEXT PRIMARY KEY,
            source_root TEXT NOT NULL,
            source_relpath TEXT NOT NULL,
            project_id TEXT NOT NULL DEFAULT '',
            project_name TEXT NOT NULL DEFAULT '',
            file_size INTEGER NOT NULL,
            mtime_ns INTEGER NOT NULL,
            status TEXT NOT NULL,
            image_id INTEGER REFERENCES images(id),
            error TEXT NOT NULL DEFAULT ''
        );
        CREATE INDEX IF NOT EXISTS sources_image_idx ON sources(image_id);
    ''')
    return db


def upsert_source(db, path, root, stat, status, image_id=None, error=''):
    project_id, project_name = project_info(root)
    db.execute('''INSERT INTO sources
        (source_path,source_root,source_relpath,project_id,project_name,file_size,mtime_ns,status,image_id,error)
        VALUES (?,?,?,?,?,?,?,?,?,?)
        ON CONFLICT(source_path) DO UPDATE SET
        source_root=excluded.source_root, source_relpath=excluded.source_relpath,
        project_id=excluded.project_id, project_name=excluded.project_name,
        file_size=excluded.file_size, mtime_ns=excluded.mtime_ns,
        status=excluded.status, image_id=excluded.image_id, error=excluded.error''',
        (str(path), str(root), str(path.relative_to(root)), project_id, project_name,
         stat.st_size, stat.st_mtime_ns, status, image_id, error))


def next_filename(db, output):
    """Never reuse an output name, including names already on disk."""
    max_id = db.execute('SELECT COALESCE(MAX(id),0) FROM images').fetchone()[0]
    # Normally equal to newly assigned id. We also skip pre-existing or unrelated files.
    n = max_id
    while True:
        n += 1
        name = f'L3_{n:05d}.dcm'
        if not (output / name).exists() and not db.execute(
                'SELECT 1 FROM images WHERE output_filename=?', (name,)).fetchone():
            return name


def index_existing(db, output):
    """Import legacy copied images, retaining their names, before starting new work."""
    imported = 0
    for p in sorted(output.glob('L3_*.dcm')):
        # Skip any file already registered by name.
        if db.execute('SELECT 1 FROM images WHERE output_filename=?', (p.name,)).fetchone():
            continue
        try:
            ds = pydicom.dcmread(p, stop_before_pixels=True)
            if get_value(ds, 'Modality').upper() != 'CT':
                continue
            key = dedup_key(ds, p)
            meta = {k: get_value(ds,k) for k in METADATA}
            country, basis = country_info(meta)
            db.execute('''INSERT OR IGNORE INTO images
                (dedup_key,output_filename,status,byte_size,meta_json,country,country_basis)
                VALUES (?,?,?,?,?,?,?)''',
                (key, p.name, 'COMPLETE', p.stat().st_size, json.dumps(meta,ensure_ascii=False), country, basis))
            imported += db.execute('SELECT changes()').fetchone()[0]
        except (OSError, ValueError, pydicom.errors.InvalidDicomError) as e:
            print(f'WARNING: cannot import existing file {p}: {e}', file=sys.stderr)
    db.commit()
    return imported


def copy_atomic(source, dest):
    # Same-directory temp file => os.replace is atomic within the filesystem.
    temp = dest.with_name(dest.name + '.partial')
    try:
        with source.open('rb') as src, temp.open('wb') as dst:
            while True:
                buf = src.read(1024 * 1024)
                if not buf:
                    break
                dst.write(buf)
            dst.flush()
            os.fsync(dst.fileno())
        # Validate destination size; verify against the stable source size as well.
        if temp.stat().st_size != source.stat().st_size:
            raise OSError(f'Copy size mismatch: {source}')
        os.replace(temp, dest)
    finally:
        if temp.exists():
            temp.unlink()


def finish_pending(db, output):
    """Reconcile process death between copy completion and DB commit."""
    n = 0
    for iid, key, name, expected in db.execute(
            "SELECT id,dedup_key,output_filename,byte_size FROM images WHERE status='PENDING'").fetchall():
        dest = output / name
        tmp = output / (name + '.partial')
        if tmp.exists():
            tmp.unlink()  # Never accept an incomplete copy.
        if dest.is_file() and dest.stat().st_size == expected:
            try:
                ds = pydicom.dcmread(dest, stop_before_pixels=True)
                if dedup_key(ds, dest) == key:
                    db.execute("UPDATE images SET status='COMPLETE' WHERE id=?", (iid,))
                    db.execute("UPDATE sources SET status='COPIED' WHERE image_id=?", (iid,))
                    n += 1
                    continue
            except Exception:
                pass
        # Missing/inconsistent file: retain pending slot, retry from a source when encountered.
        if dest.exists():
            print(f'WARNING: incomplete/unverified destination {dest}; manual inspection required', file=sys.stderr)
    db.commit()
    return n


def process_file(db, path, root, output, counts):
    stat = path.stat()
    old = db.execute('SELECT file_size,mtime_ns,status,image_id FROM sources WHERE source_path=?',
                     (str(path),)).fetchone()
    if old and old[0:2] == (stat.st_size,stat.st_mtime_ns) and old[2] not in ('ERROR', 'PENDING'):
        # A changed project list may associate the same exact file with another root;
        # keep the first root for this path, but don't drop its original provenance.
        counts['already_processed'] += 1
        return
    try:
        ds = pydicom.dcmread(path, stop_before_pixels=True)
        if get_value(ds, 'Modality').upper() != 'CT':
            with db:
                upsert_source(db,path,root,stat,'NON_CT')
            counts['non_ct'] += 1
            return
        key = dedup_key(ds, path)
        meta = {k:get_value(ds,k) for k in METADATA}
        record = db.execute('SELECT id,output_filename,status FROM images WHERE dedup_key=?', (key,)).fetchone()
        if record is None:
            country, basis = country_info(meta)
            # One short transaction reserves a unique ID and destination in database.
            with db:
                name = next_filename(db, output)
                cur = db.execute('''INSERT INTO images
                    (dedup_key,output_filename,status,byte_size,meta_json,country,country_basis)
                    VALUES (?,?,'PENDING',?,?,?,?)''',
                    (key,name,stat.st_size,json.dumps(meta,ensure_ascii=False),country,basis))
                image_id = cur.lastrowid
                upsert_source(db,path,root,stat,'PENDING',image_id)
            status = 'PENDING'
        else:
            image_id,name,status = record
            if status == 'COMPLETE':
                # Validate output presence before claiming deduplication.
                if (output/name).is_file():
                    with db:
                        upsert_source(db,path,root,stat,'DUPLICATE',image_id)
                    counts['duplicates'] += 1
                    return
                status = 'PENDING'
                with db:
                    db.execute("UPDATE images SET status='PENDING' WHERE id=?",(image_id,))
            with db:
                upsert_source(db,path,root,stat,'PENDING',image_id)
        dest = output/name
        # A stale/unverified completed destination must not be overwritten silently.
        if dest.exists():
            raise OSError(f'Destination exists but not verified: {dest}')
        copy_atomic(path,dest)
        with db:
            db.execute("UPDATE images SET status='COMPLETE', byte_size=? WHERE id=?",
                       (stat.st_size,image_id))
            upsert_source(db,path,root,stat,'COPIED',image_id)
        counts['copied'] += 1
    except (OSError, ValueError, pydicom.errors.InvalidDicomError) as exc:
        with db:
            upsert_source(db,path,root,stat,'ERROR',None,f'{type(exc).__name__}: {exc}')
        counts['errors'] += 1
        print(f'WARNING: {path}: {exc}', file=sys.stderr)


def export_csv(db, output):
    image_fields = ['image_id','output_filename','dedup_key','byte_size','country','country_basis'] + METADATA
    with (output/'images.csv').open('w',newline='',encoding='utf-8-sig') as f:
        w = csv.DictWriter(f,fieldnames=image_fields)
        w.writeheader()
        for iid,name,key,size,meta_json,country,basis in db.execute('''
            SELECT id,output_filename,dedup_key,byte_size,meta_json,country,country_basis
            FROM images WHERE status='COMPLETE' ORDER BY id'''):
            row = {'image_id':f'L3_{iid:05d}','output_filename':name,'dedup_key':key,
                   'byte_size':size,'country':country,'country_basis':basis}
            row.update(json.loads(meta_json))
            w.writerow(row)
    fields = ['source_path','source_root','source_relpath','project_id','project_name',
              'file_size','mtime_ns','status','image_id','output_filename','error']
    with (output/'image_sources.csv').open('w',newline='',encoding='utf-8-sig') as f:
        w = csv.DictWriter(f,fieldnames=fields)
        w.writeheader()
        for row in db.execute('''SELECT s.source_path,s.source_root,s.source_relpath,
            s.project_id,s.project_name,s.file_size,s.mtime_ns,s.status,s.image_id,
            i.output_filename,s.error FROM sources s
            LEFT JOIN images i ON s.image_id=i.id ORDER BY s.source_path'''):
            d = dict(zip(fields,row))
            d['image_id'] = f'L3_{d["image_id"]:05d}' if d['image_id'] is not None else ''
            w.writerow(d)
    with (output/'scan_errors.csv').open('w',newline='',encoding='utf-8-sig') as f:
        w = csv.writer(f)
        w.writerow(['source_path','error'])
        w.writerows(db.execute("SELECT source_path,error FROM sources WHERE status='ERROR' ORDER BY source_path"))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('project_folders', type=Path)
    parser.add_argument('output_folder', type=Path)
    args=parser.parse_args()
    roots=resolve_roots(args.project_folders)
    output=args.output_folder.expanduser().resolve()
    if any(output==root for root in roots):
        parser.error('Output folder must not equal any source root')
    output.mkdir(parents=True,exist_ok=True)
    db=open_db(output/'l3_registry.sqlite3')
    counts={'copied':0,'duplicates':0,'already_processed':0,'non_ct':0,'errors':0}
    try:
        imported=index_existing(db,output)
        recovered=finish_pending(db,output)
        print(f'Existing images indexed: {imported}; interrupted copies recovered: {recovered}', flush=True)
        visited=set()
        for root in roots:
            print(f'Scanning {root}',flush=True)
            for path in root.rglob('*'):
                if not path.is_file():
                    continue
                resolved=path.resolve()
                if resolved==output or output in resolved.parents or resolved in visited:
                    continue
                visited.add(resolved)
                process_file(db,path,root,output,counts)
                if (sum(counts.values()) % 500)==0:
                    print(f'Processed: {sum(counts.values())}; copied: {counts["copied"]}; duplicates: {counts["duplicates"]}',flush=True)
    except KeyboardInterrupt:
        print('\nInterrupted. Registry saved; rerun the same command to resume.',file=sys.stderr)
    finally:
        export_csv(db,output)
        db.close()
    print('Run statistics:',counts)
    print('Registry:',output/'l3_registry.sqlite3')
    print('Exports:',output/'images.csv', 'and', output/'image_sources.csv')

if __name__=='__main__':
    main()
