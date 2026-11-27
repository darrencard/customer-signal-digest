#!/usr/bin/env python3
"""Write the Acme sample's customer feedback into examples/acme/feedback/.

Acme is an invented company: invoicing software for trades businesses. Its quote drafting assistant shipped on
2026-09-07. Every account, name, email, phone number, card number, ARR figure and quote here is invented and
illustrative; the card numbers are published test numbers. The files are shaped like each system's documented
export: Zendesk ticket pages with sideloaded users, Intercom conversation search results, and CSV exports of call
notes and NPS answers.

On purpose, the feedback carries: a ticket repeated on two pages, one complaint sent by ticket and then by chat,
personal data of the kinds the redactor handles, an NPS score with no comment, and one signal on each side of the
2026-09-07 to 2026-11-24 window.

Usage, from the repo root:
  python3 evals/make_sample.py
"""

from __future__ import annotations

import csv
import datetime
import json
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "examples" / "acme" / "feedback"


def epoch(day: str, hour: int = 9) -> int:
    return int(datetime.datetime.fromisoformat(f"{day}T{hour:02d}:00:00+00:00").timestamp())


def ticket(tid: int, day: str, org: int, user: int, subject: str, description: str, tags: list[str]) -> dict:
    return {"id": tid, "created_at": f"{day}T09:00:00Z", "organization_id": org, "requester_id": user, "subject": subject, "description": description, "tags": tags}


USERS = [
    {"id": 501, "name": "Priya Raman", "email": "priya.raman@harbourplumbing.example"},
    {"id": 502, "name": "Tom Okafor", "email": "tom@okaforelectrical.example"},
    {"id": 503, "name": "Grace Lindqvist", "email": "grace@lindqvistroofing.example"},
    {"id": 504, "name": "Ahmed Siddiqui", "email": "ahmed@siddiquibuild.example"},
    {"id": 505, "name": "Owen Hughes", "email": "owen@hughesheating.example"},
    {"id": 508, "name": "Maya Fischer", "email": "maya@fischertiling.example"},
    {"id": 509, "name": "Luis Moreno", "email": "luis@morenoglazing.example"},
    {"id": 516, "name": "Hana Kim", "email": "hana@kimlandscapes.example"},
]

PAGE_1 = [
    ticket(
        4101,
        "2026-11-20",
        9001,
        501,
        "Quote draft left off the materials",
        "The assistant drafted a quote for a boiler swap and left off half the line items. Copper pipe and fittings were missing. "
        "Call me on 604-555-0142 or email priya.raman@harbourplumbing.example.\n\nThanks,\nPriya Raman",
        ["theme:quote-line-items"],
    ),
    ticket(
        4102,
        "2026-11-18",
        9002,
        502,
        "Reminder went to a customer who already paid",
        "Your invoice chaser emailed my customer a reminder even though they already paid by card ending 4242 last week. Very embarrassing. My name is Tom Okafor.",
        ["theme:chaser-paid-invoices"],
    ),
    ticket(
        4103,
        "2026-11-12",
        9003,
        503,
        "Missing line items again",
        "Third quote this month where the draft is missing line items for labour. Card on file is 4111 1111 1111 1111 if you need to refund the month.",
        [],
    ),
    ticket(
        4104,
        "2026-10-02",
        9004,
        504,
        "Accounting export tax code wrong",
        "The accounting export puts the wrong tax code on every labour line. Our bookkeeper has to fix it by hand each month.",
        ["theme:accounting-export"],
    ),
    ticket(
        4108, "2026-10-14", 9005, 505, "Labour missing from the quote draft", "The quote draft missed the labour line items on a radiator job. I typed them in again at 10pm.", []
    ),
]
PAGE_2 = [
    PAGE_1[0],  # the same ticket, returned again on the next page
    ticket(4105, "2026-10-22", 9009, 509, "Job notes lost offline", "Mobile app lost my job notes when I went offline in a basement. They never synced.", ["theme:offline-sync"]),
    ticket(4109, "2026-10-01", 9008, 508, "Call-out fee left off", "The quote draft left off the call-out fee line item, so we under-quoted a job.", []),
    ticket(4106, "2026-09-15", 9016, 516, "Dark mode", "Could the mobile app have a dark mode for early starts?", []),
]

CONVERSATIONS = [
    (
        "215001",
        "2026-11-20",
        "9001",
        "Priya Raman",
        "priya.raman@harbourplumbing.example",
        "<p>The quote draft left off the materials for the boiler swap.</p><p>Copper pipe and fittings were missing.</p>",
        ["theme:quote-line-items"],
    ),
    (
        "215002",
        "2026-11-05",
        "9007",
        "Sam Whitfield",
        "sam@whitfieldjoinery.example",
        "<p>Hi, this is Sam Whitfield from Whitfield Joinery. The drafted quote skipped the line items for hinges and handles. Ring me on +44 20 7946 0958.</p>",
        [],
    ),
    (
        "215004",
        "2026-11-10",
        "9006",
        "Dev Patel",
        "dev.patel@pateldrainage.example",
        "<p>Chasing emails keep going to clients who already paid. Please stop the reminder once the payment matches.</p>",
        [],
    ),
    ("215006", "2026-11-16", "9014", "Erin Walsh", "erin@walshdecor.example", "<p>Love that quotes go out the same day now. Customers notice.</p>", []),
]

CALLS = [
    (
        "C-301",
        "2026-11-19",
        "9010",
        "Nadia Brennan",
        "Spoke with Nadia Brennan. Their estimators stopped using AI quote drafts because line items for materials go missing. They re-key every quote.",
    ),
    (
        "C-302",
        "2026-11-10",
        "9004",
        "Ahmed Siddiqui",
        "Ahmed walked through the accounting export. Tax code on labour lines is wrong every month and the bookkeeper fixes the ledger by hand.",
    ),
    (
        "C-303",
        "2026-10-28",
        "9011",
        "Ivan Petrov",
        "Call with Ivan Petrov. Invoice chaser sent reminders after the customer had already paid. Wants chasing to stop when payment is matched.",
    ),
    ("C-305", "2026-10-08", "9013", "Ruth Adeyemi", "Ruth says quotes now go out the same day as the site visit. They won two jobs they would have lost to slower firms."),
    ("C-304", "2026-11-25", "9003", "Grace Lindqvist", "Grace says quote drafts are still missing line items for labour. Considering going back to the old template."),
]

NPS = [
    ("N-01", "2026-11-21", "9012", "3", "Quote drafts keep missing line items. I check every one by hand now."),
    ("N-03", "2026-11-08", "9006", "4", "The mobile app goes offline in basements and loses job notes. Email me at dev.patel@pateldrainage.example"),
    ("N-04", "2026-11-23", "9014", "6", "Reminders go out to customers who already paid. Stop the chase once paid please."),
    ("N-05", "2026-11-02", "9015", "8", ""),
    ("N-06", "2026-09-01", "9016", "5", "Accounting export tax codes are wrong on labour."),
    ("N-07", "2026-10-20", "9002", "10", "Quotes go out the same day now. Got my evenings back."),
    ("N-08", "2026-11-09", "9011", "9", "Drafting a quote takes minutes now, not my evenings."),
    ("N-09", "2026-09-22", "9015", "9", "Quotes take minutes now. My evenings are mine again."),
]

ACCOUNTS = [
    ("9001", 18000),
    ("9002", 9600),
    ("9003", 24000),
    ("9004", 12000),
    ("9005", 7200),
    ("9006", 10800),
    ("9007", 14400),
    ("9008", 6000),
    ("9009", 9600),
    ("9010", 30000),
    ("9011", 8400),
    ("9012", 12000),
    ("9013", 15600),
    ("9014", 4800),
    ("9015", 6000),
    ("9016", 3600),
]

THEMES = {
    "opportunities": [
        {
            "id": "quote-line-items",
            "name": "Quote drafts miss line items",
            "bet": "quote-drafting",
            "side": "problem",
            "keywords": ["line items", "line item", "left off", "quote draft", "quote drafts", "drafted quote", "re-key"],
        },
        {
            "id": "quotes-same-day",
            "name": "Quotes go out the same day",
            "bet": "quote-drafting",
            "side": "praise",
            "keywords": ["same day", "evenings", "takes minutes", "take minutes"],
        },
        {
            "id": "chaser-paid-invoices",
            "name": "Invoice chasers go to customers who already paid",
            "keywords": ["already paid", "chaser", "reminder", "reminders", "chase", "chasing"],
        },
        {"id": "offline-sync", "name": "Mobile app loses job notes offline", "keywords": ["offline", "synced", "sync"]},
        {
            "id": "accounting-export",
            "name": "Accounting export puts the wrong tax code on labour",
            "keywords": ["accounting export", "tax code", "tax codes", "ledger", "bookkeeper"],
        },
    ]
}


def write_csv(path: Path, header: list[str], rows: list[tuple]) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(header)
        w.writerows(rows)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)

    def dump(name: str, data: object) -> None:
        (OUT / name).write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    dump("zendesk-page-1.json", {"tickets": PAGE_1, "users": USERS, "next_page": "zendesk-page-2.json"})
    dump("zendesk-page-2.json", {"tickets": PAGE_2, "users": USERS, "next_page": None})
    dump(
        "intercom-conversations.json",
        {
            "type": "conversation.list",
            "conversations": [
                {"id": cid, "created_at": epoch(day), "source": {"subject": "", "body": body, "author": {"name": name, "email": email}},
                 "tags": {"tags": [{"name": t} for t in tags]}, "custom_attributes": {"account_id": acct}}
                for cid, day, acct, name, email, body, tags in CONVERSATIONS
            ],
            "pages": {"type": "pages", "page": 1, "total_pages": 1},
        },
    )  # fmt: skip
    write_csv(OUT / "calls.csv", ["call_id", "date", "account", "contact", "notes"], CALLS)
    write_csv(OUT / "nps.csv", ["response_id", "submitted_at", "account", "score", "comment"], NPS)
    write_csv(OUT / "accounts.csv", ["account", "arr"], ACCOUNTS)
    dump("themes.json", THEMES)
    print(f"make_sample: wrote the Acme feedback to {OUT}")


if __name__ == "__main__":
    main()
