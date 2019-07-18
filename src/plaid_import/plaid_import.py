import json
import re
import sys
from datetime import datetime
from os import environ

from dotenv import load_dotenv
from plaid import Client
from tqdm import tqdm


def fetch_plaid_transactions(access_token):
    client = Client(
        client_id=environ["PLAID_CLIENT_ID"],
        secret=environ["PLAID_SECRET"],
        public_key=environ["PLAID_PUBLIC_KEY"],
        environment=environ["PLAID_ENV"],
    )

    start_date = "2019-01-01"
    end_date = datetime.today().strftime("%Y-%m-%d")

    response = client.Transactions.get(
        access_token, start_date=start_date, end_date=end_date
    )
    accounts = {account["account_id"]: account for account in response["accounts"]}
    total = response["total_transactions"]
    transactions = response["transactions"]

    with tqdm(total=total) as pbar:
        pbar.update(len(transactions))
        while len(transactions) < total:
            response = client.Transactions.get(
                access_token,
                start_date=start_date,
                end_date=end_date,
                offset=len(transactions),
            )
            transactions.extend(response["transactions"])
            pbar.update(len(response["transactions"]))
    return {"accounts": accounts, "transactions": transactions}


def write_plaid_transactions(data):
    with open("data.json", "w") as stream:
        stream.write(json.dumps(data))


def load_plaid_transactions():
    with open("data.json", "r") as stream:
        return json.load(stream)


def execute_rules(rules, hledger_transaction):
    for rule in rules:
        if rule["pattern"].search(hledger_transaction["description"]):
            for key, value in rule["set"].items():
                if key.startswith("account"):
                    hledger_transaction[key]["name"] = value
    return hledger_transaction


def convert_to_hledger_transaction(db, transaction):
    hledger_transaction = {}
    hledger_transaction["date"] = transaction["date"]
    hledger_transaction["description"] = transaction["name"]
    hledger_transaction["account1"] = {
        "name": db["accounts"][transaction["account_id"]],
        "amount": transaction["amount"],
    }
    hledger_transaction["account2"] = {
        "name": "expenses:unknown",
        "amount": -transaction["amount"],
    }
    return hledger_transaction


def _get_length_spacing(accounts):
    longest_account_name = max([len(account["name"]) for account in accounts])
    return [
        (
            abs(longest_account_name - len(account["name"]))
            + (1 if account["amount"] > 0 else 0)
        )
        for account in accounts
    ]


def print_transaction_to_hledger(transaction):
    date = transaction["date"]
    description = transaction["description"]

    print(f"{date} {description}")

    accounts = [transaction[key] for key in transaction if key.startswith("account")]
    for account, length_spaces in zip(accounts, _get_length_spacing(accounts)):
        account_name = account["name"]
        amount = account["amount"]
        print(f"    {account_name}{' ' * length_spaces}    {amount}")
    print()


def main():
    load_dotenv()

    with open("db.json", "r") as db_file:
        db = json.load(db_file)

    # access_token = environ["PLAID_ACCESS_TOKEN"]
    # data = fetch_plaid_transactions(access_token)
    # write_plaid_transactions(data)
    data = load_plaid_transactions()

    for transaction in sorted(
        data["transactions"], key=lambda t: datetime.strptime(t["date"], "%Y-%m-%d")
    ):
        account1 = db["accounts"].get(transaction["account_id"])
        if account1 is None:
            transaction_id = transaction["transaction_id"]
            account_name = data["accounts"][transaction["account_id"]]["name"]
            print(
                f"Transaction {transaction_id} has an unknown account '{account_name}', skipping.",
                file=sys.stderr,
            )
            continue
        precompiled_rules = [
            {"pattern": re.compile(rule["match"], re.I), "set": rule["set"]}
            for rule in db["rules"]
        ]
        hledger_transaction = convert_to_hledger_transaction(db, transaction)
        result = execute_rules(precompiled_rules, hledger_transaction)
        print_transaction_to_hledger(result)
        db["transactions_imported"].append(transaction["transaction_id"])
