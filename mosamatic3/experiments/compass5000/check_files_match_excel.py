import os
import json
import numpy as np
import pandas as pd

DATA_DIR = "H:\\COMPASS_raw_data_v1"
EXCEL_FILE = "H:\\COMPASS_accesionnumbers_V3_pseudo_28082026.xlsx"

def main():
  
  df = pd.read_excel(EXCEL_FILE)
  ids_xlsx = list(np.unique(df["pseudoID"]))
  print(f'Nr. patients Excel: {len(ids_xlsx)}')

  ids_zips = {}
  for f in os.listdir(DATA_DIR):
    items = f.split("-")
    compass_id = f"{items[2]}-{items[3]}"
    if compass_id not in ids_zips.keys():
      ids_zips[compass_id] = 0
    ids_zips[compass_id] += 1

  print(json.dumps(ids_zips, indent=4))
  print(f'Nr. patients: {len(ids_zips.keys())}')

  only_in_xlsx = list(set(ids_xlsx) - set(ids_zips))
  only_in_zips = list(set(ids_zips) - set(ids_xlsx))

  print(f"In XLSX but not in ZIPS:")
  for item in only_in_xlsx:
    print(item)
  print(f"In ZIPS but not in XLSX :{only_in_zips}")



if __name__ == '__main__':
  main()