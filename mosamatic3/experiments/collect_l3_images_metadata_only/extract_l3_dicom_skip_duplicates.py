#!/usr/bin/env python3
"""Identify likely L3 single-slice CT DICOMs from metadata; copy with audit CSV.

Usage: python extract_l3_dicom.py ROOT_FOLDER OUTPUT_FOLDER

Classification is a PROXY based on scan region, not verified vertebral anatomy.
"""
import argparse
import csv
import hashlib
import re
import shutil
from collections import Counter
from pathlib import Path

import pydicom

# Customize for your site's protocol vocabulary after reviewing UNKNOWN cases.
CHEST = [r'\bthorax\b', r'\bthoracic\b', r'\bchest\b', r'\blung(?:s)?\b',
         r'\bpulmonary\b', r'\bthorax(?:ct)?\b', r'\bthx\b']
ABDOMEN = [r'\babdomen\b', r'\babdominal\b', r'\babd\b', r'\bupper abdomen\b',
           r'\bliver\b', r'\bpancrea(?:s|tic)\b', r'\bbovenbuik\b']

# Manually curated overrides, ONLY after checking the dataset's provenance.
# Map normalized InstitutionName values to ISO 3166-1 alpha-2 country codes.
HOSPITAL_COUNTRY = {
    # 'maastricht university medical center': 'NL',
}

# Conservative extraction from InstitutionAddress ONLY; do not guess from vendor.
COUNTRY_PATTERNS = {
    'NL': [r'\bnetherlands\b', r'\bnederland\b', r'\bholland\b'],
    'BE': [r'\bbelgium\b', r'\bbelgie\b', r'\bbelgië\b', r'\bbelgique\b'],
    'DE': [r'\bgermany\b', r'\bdeutschland\b'],
    'FR': [r'\bfrance\b'],
    'GB': [r'\bunited kingdom\b', r'\bengland\b', r'\bscotland\b', r'\bwales\b'],
    'US': [r'\bunited states\b', r'\busa\b', r'\bu\.s\.a\.\b'],
    'IT': [r'\bitaly\b', r'\bitalia\b'],
    'ES': [r'\bspain\b', r'\bespaña\b', r'\bespana\b'],
    'CH': [r'\bswitzerland\b', r'\bschweiz\b', r'\bsuisse\b'],
    'AT': [r'\baustria\b', r'\bösterreich\b', r'\boesterreich\b'],
    'DK': [r'\bdenmark\b', r'\bdanmark\b'],
    'SE': [r'\bsweden\b', r'\bsverige\b'],
    'NO': [r'\bnorway\b', r'\bnorge\b'],
    'FI': [r'\bfinland\b', r'\bsuomi\b'],
    'PL': [r'\bpoland\b', r'\bpolska\b'],
    'CA': [r'\bcanada\b'],
    'AU': [r'\baustralia\b'],
}

METADATA = [
    'Modality', 'BodyPartExamined', 'StudyDescription', 'SeriesDescription', 'ProtocolName',
    'InstitutionName', 'InstitutionAddress', 'InstitutionalDepartmentName',
    'Manufacturer', 'ManufacturerModelName', 'StationName', 'SoftwareVersions',
    'KVP', 'XRayTubeCurrent', 'Exposure', 'ExposureTime', 'ConvolutionKernel',
    'SliceThickness', 'SpacingBetweenSlices', 'PixelSpacing', 'ReconstructionDiameter',
    'ConvolutionKernelGroup', 'RescaleSlope', 'RescaleIntercept',
    'ContrastBolusAgent', 'ContrastBolusRoute', 'ImageType',
    'Rows', 'Columns', 'StudyDate', 'PatientSex', 'PatientAge',
    'StudyInstanceUID', 'SeriesInstanceUID', 'SOPInstanceUID',
]
FIELDS = ['source_relpath', 'output_filename', 'classification', 'classification_basis',
          'copy_status', 'duplicate_of', 'country', 'country_basis'] + METADATA + ['error']


def value(ds, keyword):
    result = getattr(ds, keyword, '')
    if result is None:
        return ''
    if isinstance(result, (list, tuple)) or result.__class__.__name__ == 'MultiValue':
        return '|'.join(str(v) for v in result)
    return str(result).replace('\n', ' ').replace('\r', ' ').strip()


def has_pattern(text, patterns):
    return any(re.search(p, text, re.IGNORECASE) for p in patterns)


def classify(ds):
    # A chest/abdomen CT scan can contain both anatomy descriptions. Never
    # treat the mere presence of 'abdomen' as proof of an L3 slice.
    fields = ('BodyPartExamined', 'SeriesDescription', 'ProtocolName', 'StudyDescription')
    seen = []
    for field in fields:
        text = value(ds, field)
        if not text:
            continue
        chest = has_pattern(text, CHEST)
        abdomen = has_pattern(text, ABDOMEN)
        if chest and abdomen:
            return 'UNKNOWN', f'mixed in {field}'
        if chest:
            seen.append(('T4', field))
        elif abdomen:
            seen.append(('L3', field))
    kinds = {x[0] for x in seen}
    if len(kinds) == 1:
        return seen[0][0], '+'.join(x[1] for x in seen)
    if len(kinds) > 1:
        return 'UNKNOWN', 'conflicting fields'
    return 'UNKNOWN', 'no region keywords'


def country(ds):
    hospital = value(ds, 'InstitutionName').strip().casefold()
    if hospital in HOSPITAL_COUNTRY:
        return HOSPITAL_COUNTRY[hospital], 'hospital mapping'
    address = value(ds, 'InstitutionAddress')
    matches = [code for code, patterns in COUNTRY_PATTERNS.items()
               if has_pattern(address, patterns)]
    if len(matches) == 1:
        return matches[0], 'institution address'
    return '', ''


def inside(path, parent):
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def file_hash(path):
    """Fallback for images lacking SOPInstanceUID (rare, nonconformant DICOM)."""
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def dedup_key(ds, path):
    uid = value(ds, 'SOPInstanceUID')
    return ('UID', uid) if uid else ('SHA256', file_hash(path))


def existing_l3(output):
    """Index existing L3 outputs so repeated runs also avoid duplicates."""
    seen = {}
    for path in sorted(output.glob('L3_*.dcm')):
        if not path.is_file():
            continue
        try:
            ds = pydicom.dcmread(path, stop_before_pixels=True)
            seen.setdefault(dedup_key(ds, path), path.name)
        except (OSError, ValueError, pydicom.errors.InvalidDicomError):
            continue
    return seen


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('root_folder', type=Path)
    parser.add_argument('output_folder', type=Path)
    args = parser.parse_args()
    root = args.root_folder.resolve()
    output = args.output_folder.resolve()
    if not root.is_dir():
        parser.error(f'Not a directory: {root}')
    if output == root:
        parser.error('Output folder cannot equal root folder')
    output.mkdir(parents=True, exist_ok=True)
    counts = Counter()
    seen_l3 = existing_l3(output)
    csv_path = output / 'dicom_metadata.csv'
    with csv_path.open('w', newline='', encoding='utf-8-sig') as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDS)
        writer.writeheader()
        for source in root.rglob('*'):
            if not source.is_file() or inside(source.resolve(), output):
                continue
            rel = str(source.relative_to(root))
            row = dict.fromkeys(FIELDS, '')
            row['source_relpath'] = rel
            try:
                # No pixel data loaded. No filename-extension requirement.
                ds = pydicom.dcmread(source, stop_before_pixels=True)
                if value(ds, 'Modality').upper() != 'CT':
                    counts['SKIPPED_NON_CT'] += 1
                    continue
                for keyword in METADATA:
                    row[keyword] = value(ds, keyword)
                row['classification'], row['classification_basis'] = classify(ds)
                row['country'], row['country_basis'] = country(ds)
                counts[row['classification']] += 1
                if row['classification'] == 'L3':
                    key = dedup_key(ds, source)
                    if key in seen_l3:
                        row['copy_status'] = 'DUPLICATE_SKIPPED'
                        row['duplicate_of'] = seen_l3[key]
                        counts['DUPLICATE_SKIPPED'] += 1
                    else:
                        # Preserve original bytes, and keep output names stable.
                        digest = hashlib.sha256(rel.encode('utf-8')).hexdigest()[:16]
                        dst = output / f'L3_{digest}.dcm'
                        # Avoid overwriting an unrelated existing file in a
                        # (vanishingly unlikely) filename-hash collision.
                        suffix = 1
                        while dst.exists():
                            dst = output / f'L3_{digest}_{suffix}.dcm'
                            suffix += 1
                        shutil.copy2(source, dst)
                        seen_l3[key] = dst.name
                        row['output_filename'] = dst.name
                        row['copy_status'] = 'COPIED'
                        counts['COPIED'] += 1
                writer.writerow(row)
            except (OSError, ValueError, pydicom.errors.InvalidDicomError) as exc:
                counts['UNREADABLE'] += 1
                # Record unreadable files for auditing, without failing the run.
                row['classification'] = 'UNREADABLE'
                row['error'] = f'{type(exc).__name__}: {exc}'
                writer.writerow(row)
    print('Finished:')
    for key in ('L3', 'T4', 'UNKNOWN', 'SKIPPED_NON_CT', 'UNREADABLE'):
        print(f'  {key}: {counts[key]}')
    print(f'  L3 copied: {counts["COPIED"]}')
    print(f'  L3 duplicates skipped: {counts["DUPLICATE_SKIPPED"]}')
    print(f'CSV: {csv_path}')
    print('CAUTION: L3 is a scan-region proxy, not anatomically verified L3.')


if __name__ == '__main__':
    main()
