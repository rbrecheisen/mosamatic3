#!/bin/zsh

conda activate mosamatic3
cd mosamatic3/server
pytest -v
cd ../..
