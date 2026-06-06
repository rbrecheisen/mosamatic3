def load_dicom(file_path):
    try:
        import pydicom
        return pydicom.dcmread(str(file_path), force=True)
    except Exception as exc:
        print(f'Could not load DICOM file {file_path}: {exc}')
        return None
