import csv
import os
import shutil
from datetime import datetime
from os.path import splitext


def convert_filename_to_account(filename):
    return splitext(filename)[0].replace("-", ":")


def reformat_date(date_str):
    date = datetime.strptime(date_str, "%m/%d/%Y")
    return date.strftime("%Y/%m/%d")


def clean_row(row, account_name):
    old_date, description, out_amt, in_amt, _ = row
    return [
        reformat_date(old_date),
        -float(out_amt) if out_amt else float(in_amt),
        account_name,
        "",
        description.strip(),
    ]


def clean_input_files():
    shutil.rmtree("imports/cleaned", ignore_errors=True)
    os.makedirs("imports/cleaned", exist_ok=True)

    account_names = []
    for file in os.listdir("imports/csvs"):
        account_name = convert_filename_to_account(file)
        with open("imports/csvs/" + file) as infile:
            with open("imports/cleaned/" + file, "w") as outfile:
                reader = csv.reader(infile)
                writer = csv.writer(outfile, quoting=csv.QUOTE_NONNUMERIC)
                for row in reader:
                    writer.writerow(clean_row(row, account_name))
        account_names.append(account_name)
    return account_names


def aggregate_cleaned_files():
    os.system(
        """
      xsv cat rows --no-headers {import_files} \
        | xsv sort --no-headers --select 1 \
        | xsv search --no-headers --invert-match 'PC FROM|Customer Transfer Cr.|BANK THE REST|CREDIT CARD/LOC PAY. FROM|PC - PAYMENT FROM|PAYMENT-THANK YOU SCOTIABANK' \
        | xsv fmt --quote-always --crlf -o {output_file}
    """.format(
            import_files="imports/cleaned/*.csv", output_file="imports/all.csv"
        )
    )


def hledger_read_aggregated_file():
    os.system(
        """
    hledger -f {input_csv} --rules-file {rules} print >> {journal}
    """.format(
            input_csv="imports/all.csv",
            rules="rules/all.rules",
            journal=".hledger.journal",
        )
    )


def output_last_imported(accounts):
    os.remove("imports/last_import.txt")
    for account in accounts:
        os.system(
            """
      echo "{account} `hledger reg {account} | tail -n 1 | cut -d' ' -f1`" >> {last_import_file}
      """.format(
                account=account, last_import_file="imports/last_import.txt"
            )
        )


def main():
    accounts = clean_input_files()
    aggregate_cleaned_files()
    hledger_read_aggregated_file()
    output_last_imported(accounts)
