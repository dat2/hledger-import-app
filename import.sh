./aggregate_csvs.py
hledger -f "imports/all.csv" --rules-file "rules/all.rules" print >> .hledger.journal
rm imports/last_import.txt
echo "chequing `hledger reg assets:chequing | tail -n 1 | cut -d' ' -f1`" >> imports/last_import.txt
echo "scene `hledger reg visa:scene | tail -n 1 | cut -d' ' -f1`" >> imports/last_import.txt
echo "momentum `hledger reg visa:momentum | tail -n 1 | cut -d' ' -f1`" >> imports/last_import.txt
