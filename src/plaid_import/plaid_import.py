import json
import re
import sys
from datetime import datetime
from os import environ
from pathlib import Path

import click
import toml
from tqdm import tqdm

from dotenv import load_dotenv
from plaid import Client


def _get_plaid_client():
    return Client(
        client_id=environ["PLAID_CLIENT_ID"],
        secret=environ["PLAID_SECRET"],
        public_key=environ["PLAID_PUBLIC_KEY"],
        environment=environ["PLAID_ENV"],
    )


def fetch_plaid_transactions(start_date):
    client = _get_plaid_client()
    end_date = datetime.today().strftime("%Y-%m-%d")

    for access_token in environ["PLAID_ACCESS_TOKENS"].split(","):
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

    len_pending = sum(1 for t in transactions if t["pending"])
    click.echo(f"Skipped {len_pending} pending transactions.")
    transactions = [t for t in transactions if not t["pending"]]
    return {"accounts": accounts, "transactions": transactions}


def save_db(data):
    db_path = Path.home() / ".plaid-import" / "db.json"
    with open(str(db_path), "w") as stream:
        json.dump(data, stream)


def load_db():
    db_path = Path.home() / ".plaid-import" / "db.json"
    with open(str(db_path), "r") as stream:
        return json.load(stream)


def execute_rules(rules, hledger_transaction):
    for rule in rules:
        if rule["pattern"].search(hledger_transaction["description"]):
            for key, value in rule["then"].items():
                if key.startswith("account"):
                    hledger_transaction[key]["name"] = value
    return hledger_transaction


def convert_to_hledger_transaction(config, transaction):
    hledger_transaction = {}
    hledger_transaction["date"] = transaction["date"]
    hledger_transaction["description"] = transaction["name"]
    hledger_transaction["account1"] = {
        "name": config["accounts"][transaction["account_id"]],
        "amount": -transaction["amount"],
    }
    hledger_transaction["account2"] = {
        "name": "expenses:unknown",
        "amount": transaction["amount"],
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

    click.echo(f"{date} {description}")

    accounts = [transaction[key] for key in transaction if key.startswith("account")]
    for account, length_spaces in zip(accounts, _get_length_spacing(accounts)):
        account_name = account["name"]
        amount = account["amount"]
        click.echo(f"    {account_name}{' ' * length_spaces}    {amount:.2f}")
    click.echo()


def get_date_from_transaction(transaction):
    return datetime.strptime(transaction["date"], "%Y-%m-%d")


@click.group()
def cli():
    """
    Fetch transactions from plaid and print them into an hledger format.
    This will also allow you to match against transaction descriptions and assign
    them to hledger accounts automatically.
    """
    load_dotenv()


def start_date_option():
    return click.option(
        "-s",
        "--start",
        "start_date",
        type=click.DateTime(formats=["%Y-%m-%d", "%Y/%m/%d"]),
        required=False,
        help="Date to start fetching transactions from.",
    )


@cli.command(name="print")
@start_date_option()
def print_(start_date=None):
    """
    Print the transactions in hledger format.
    """
    with open("config.toml", "r") as config_file:
        config = toml.load(config_file)

    data = load_db()

    transactions = sorted(data["transactions"], key=get_date_from_transaction)
    if start_date is not None:
        transactions = [
            t for t in transactions if get_date_from_transaction(t) >= start_date
        ]

    for transaction in transactions:
        account1 = config["accounts"].get(transaction["account_id"])
        if account1 is None:
            transaction_id = transaction["transaction_id"]
            account_name = data["accounts"][transaction["account_id"]]["name"]
            print(
                f"Transaction {transaction_id} has an unknown account '{account_name}', skipping.",
                file=sys.stderr,
            )
            continue
        precompiled_rules = [
            {"pattern": re.compile(rule["if"], re.I), "then": rule["then"]}
            for rule in config["rules"]
        ]
        hledger_transaction = convert_to_hledger_transaction(config, transaction)
        result = execute_rules(precompiled_rules, hledger_transaction)
        print_transaction_to_hledger(result)


@cli.command()
@start_date_option()
def fetch(start_date=None):
    """
    Fetch the latest data from plaid.
    """
    db = load_db()
    if start_date is None and db["transactions"]:
        start_date = max(db["transactions"], key=get_date_from_transaction)["date"]
    else:
        start_date = datetime.now().replace(day=1, month=1).strftime("%Y-%m-%d")
    imported_transaction_ids = {t["transaction_id"] for t in db["transactions"]}
    data = fetch_plaid_transactions(start_date)
    db["accounts"] = {**db["accounts"], **data["accounts"]}
    db["transactions"].extend(
        [
            transaction
            for transaction in data["transactions"]
            if transaction["transaction_id"] not in imported_transaction_ids
        ]
    )
    save_db(db)


@cli.command()
@click.argument("access_token")
def create_public_token(access_token):
    client = _get_plaid_client()
    click.echo(client.Item.public_token.create(access_token))


@cli.command()
@click.argument("public_token")
def create_access_token(public_token):
    client = _get_plaid_client()
    click.echo(client.Item.public_token.exchange(public_token))
