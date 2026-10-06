import json
import math
from pathlib import Path

import pandas as pd
from django.contrib.auth.decorators import login_required
from django.shortcuts import render


def _clean_value(value):
    if pd.isna(value):
        return None
    if hasattr(value, 'isoformat'):
        return value.isoformat()
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    if hasattr(value, 'item'):
        value = value.item()
    return value if isinstance(value, (str, int, float, bool)) else str(value)


@login_required
def visual_analytics(request):
    config_path = Path(__file__).resolve().parent / 'config' / 'preoperative_variables.json'
    with config_path.open('r', encoding='utf-8') as handle:
        preoperative_config = json.load(handle)

    context = {
        'cohort_json': 'null',
        'preoperative_config_json': json.dumps(preoperative_config).replace('</', '<\\/'),
        'load_error': None,
    }
    if request.method == 'POST':
        upload = request.FILES.get('cohort_file')
        if not upload:
            context['load_error'] = 'Choose an Excel cohort file first.'
        elif Path(upload.name).suffix.lower() not in {'.xlsx', '.xlsm', '.xls'}:
            context['load_error'] = 'Please upload an Excel file (.xlsx, .xlsm or .xls).'
        else:
            try:
                workbook = pd.ExcelFile(upload)
                sheet = request.POST.get('sheet_name') or workbook.sheet_names[0]
                if sheet not in workbook.sheet_names:
                    sheet = workbook.sheet_names[0]
                frame = pd.read_excel(workbook, sheet_name=sheet)
                frame = frame.dropna(how='all')
                frame.columns = [str(c).strip() for c in frame.columns]
                # JSON sent to the browser; cap only absurdly wide/large uploads, not normal cohorts.
                if len(frame) > 10000:
                    raise ValueError('The prototype currently supports cohorts up to 10,000 rows.')
                rows = [{col: _clean_value(value) for col, value in row.items()} for row in frame.to_dict('records')]
                payload = {
                    'filename': upload.name,
                    'sheet': sheet,
                    'sheets': workbook.sheet_names,
                    'columns': list(frame.columns),
                    'rows': rows,
                }
                context['cohort_json'] = json.dumps(payload).replace('</', '<\\/')
            except Exception as exc:
                context['load_error'] = f'Could not read cohort Excel: {exc}'
    return render(request, 'visualanalytics/visual_analytics.html', context)
