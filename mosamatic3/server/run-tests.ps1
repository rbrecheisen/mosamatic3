$env:MOSAMATIC_TEST_ABDOMEN_PATH = "G:\My Drive\data\Mosamatic\testdata\CT\abdomen"
python -m pytest tests/test_sliceselect_resume.py -s -m integration