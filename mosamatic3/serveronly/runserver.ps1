conda activate mosamatic3

$env:PYTHONPATH = "D:\SoftwareDevelopment\GitHub\mosamatic3\;$env:PYTHONPATH"

python manage.py migrate --noinput
python manage.py collectstatic --noinput
python manage.py ensure_admin
python manage.py runserver