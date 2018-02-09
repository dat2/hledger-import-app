#!/bin/bash
IN_FILES=imports/csvs/*.csv
CLEAN_DIR=imports/cleaned
CLEANED_FILES=$CLEAN_DIR/*.csv
OUT_FILE=imports/all.csv

function copy_input_files_to_clean_dir {
  for FILE in $IN_FILES
  do
    cp $FILE $CLEAN_DIR/${FILE##*/}
  done
}

function reformat_mdy_to_ymd {
  gdate -d"$1" +%Y/%m/%d
}

function reformat_dates_in_clean_dir {
  for FILE in $CLEANED_FILES
  do
    gsed "s#^[^,]*#$(reformat_mdy_to_ymd)#" $FILE
  done
}

function aggregate_cleaned_files {
  xsv cat rows --no-headers $CLEANED_FILES \
    | xsv sort --no-headers --select 1 \
    | xsv search --no-headers --invert-match 'PC FROM|Customer Transfer Cr.|BANK THE REST|CREDIT CARD/LOC PAY. FROM|PC - PAYMENT FROM|PAYMENT-THANK YOU SCOTIABANK' \
    | xsv fmt --quote-always --crlf -o $OUT_FILE
}

reformat_dates_in_clean_dir
