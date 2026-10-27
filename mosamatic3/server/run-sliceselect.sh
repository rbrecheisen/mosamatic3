#!/bin/bash

docker compose -f docker-compose-dev.yml exec web python manage.py batch_slice_select /scan_input/scan_folders.txt --output-dir /scan_output