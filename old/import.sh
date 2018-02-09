#!/bin/bash
OUT_FILE=$1
RULES_FILE=$2
shift
shift
IN_FILES=$@

SCRIPT_DIR="$(cd "$( dirname "$0" )" && pwd)"

# using XSV, merge files into a date sorted CSV for hledger to read in
$SCRIPT_DIR/aggregate_csvs.sh $OUT_FILE $IN_FILES

# hledger, read in the CSV file and generate a journal file for hledger to understand
hledger -f $OUT_FILE --rules-file $RULES_FILE print >> .hledger.journal

rm imports/last_import.txt
echo "chequing `hledger reg assets:chequing | tail -n 1 | cut -d' ' -f1`" >> imports/last_import.txt
echo "scene `hledger reg visa:scene | tail -n 1 | cut -d' ' -f1`" >> imports/last_import.txt
echo "momentum `hledger reg visa:momentum | tail -n 1 | cut -d' ' -f1`" >> imports/last_import.txt
