#!/usr/local/bin/python3

import argparse
import math
import os
import csv
import datetime

# complain about arguments
parser = argparse.ArgumentParser(description='Aggregate CSVs for multiple accounts for easier hledger import.')
parser.add_argument('--file', default='all', help='The name of the journal file to import')
args = parser.parse_args()

# file is the first argument
file = args.file

IMPORT_DIR = 'imports'
# given a file name, return the account associated with it
def get_account_name(import_file):
    accounts = import_file[:-len('.csv')].split('-')
    return ':'.join(accounts)

# filter out invalid rows
def is_valid_row(account_name, row):
    # don't allow transactions of 0.00
    if math.isclose(float(row[1]), 0.0):
        return False

    # to make things easier, remove the "receiving" accounts duplicated transactions

    # don't allow transfers from savings in chequing accounts
    if 'chequing' in account_name:
        return not(contains(row[4], 'PC FROM') or contains(row[3], 'Customer Transfer Cr.'))

    # don't allow bank the rest in savings accounts
    if 'savings' in account_name:
        return not(contains(row[4], 'BANK THE REST') or contains(row[4], 'PC FROM'))

    # don't allow payments from other accounts in credit accounts
    if 'credit' in account_name:
        return not(contains(row[4], 'CREDIT CARD/LOC PAY. FROM') or contains(row[4], 'PC - PAYMENT FROM') or contains(row[4], 'PAYMENT-THANK YOU SCOTIABANK'))

    # otherwise its good
    return True

# returns true if substring is in string (case insensitive)
def contains(string, substring):
    return substring.lower() in string.lower()

# attach the account to the row
def process_row(account_name, row):
    row[2] = account_name
    row[3] = row[3].strip()
    row[4] = row[4].strip()

    # change GST to GST Credit
    if contains(row[3], 'GST'):
        row[3] = 'GST Credit'

    return row

# get all the downloaded csv files
import_files = [import_file for import_file in os.listdir(IMPORT_DIR) if not import_file.startswith(file) and import_file.endswith('.csv')]

# add all the csv files in one large array
# it also does filter and map
rows = []
for import_file in import_files:
    with open(IMPORT_DIR + '/' + import_file, newline='') as csv_file:
        reader = csv.reader(csv_file, delimiter = ',')
        account_name = get_account_name(import_file)
        for row in reader:
            if is_valid_row(account_name, row):
                rows.append(process_row(account_name, row))

# sort by date
result = sorted(rows, key = lambda row: datetime.datetime.strptime(row[0], '%Y/%m/%d'))

# write the files out to the aggregated file
out_file_name = IMPORT_DIR + '/' + file + '.csv'
with open(out_file_name, 'w', newline='') as out_file:
    writer = csv.writer(out_file, delimiter=',', quoting=csv.QUOTE_ALL)
    writer.writerows(result)
