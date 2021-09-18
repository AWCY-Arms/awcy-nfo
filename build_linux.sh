pyinstaller entry_point.py \
--noconfirm \
--name awcynfo \
--add-data awcy_nfo/headers/vandal.txt:awcy_nfo/headers \
--add-data awcy_nfo/headers/royal.txt:awcy_nfo/headers \
--add-data awcy_nfo/headers/poki.txt:awcy_nfo/headers \
--add-data awcy_nfo/headers/chilled.txt:awcy_nfo/headers \
--add-data awcy_nfo/headers/bloody.txt:awcy_nfo/headers \
--add-data awcy_nfo/styles/classic.yaml:awcy_nfo/styles \
--add-data awcy_nfo/docs/example.yaml:awcy_nfo/docs