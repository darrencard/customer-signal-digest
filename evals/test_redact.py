"""Redaction: every kind of personal data is removed before anything is quoted, and ordinary text survives.

Usage:
  python3 -m unittest discover -s evals -v
"""

from __future__ import annotations

import unittest

from helpers import redact


class RedactKinds(unittest.TestCase):
    def check(self, text: str, label: str, gone: str, known: tuple[str, ...] = ()) -> None:
        out, counts = redact.redact(text, known)
        self.assertNotIn(gone, out)
        self.assertIn(f"[{label}]", out)
        self.assertGreaterEqual(counts[label], 1)
        self.assertEqual(redact.leaks(out, known), [])

    def test_email(self) -> None:
        self.check("Write to jo.bloggs+acme@example.co.uk today.", "EMAIL", "jo.bloggs")

    def test_url_with_token(self) -> None:
        self.check("See https://portal.example/t?id=8&token=abc123 for it.", "URL", "abc123")

    def test_card_passing_luhn(self) -> None:
        self.check("Card 4111 1111 1111 1111 on file.", "CARD", "4111")

    def test_phone_formats(self) -> None:
        for phone in ("604-555-0142", "(604) 555-0142", "+44 20 7946 0958", "020 7946 0958", "+1 604 555 0199"):
            with self.subTest(phone=phone):
                self.check(f"Ring me on {phone} after five.", "PHONE", phone)

    def test_iban_ip_postcode_address(self) -> None:
        self.check("Pay GB82 WEST 1234 5698 7654 32 please.", "IBAN", "WEST 1234")
        self.check("Login from 192.168.10.24 failed.", "IP", "192.168")
        self.check("Send it to SW1A 1AA.", "POSTCODE", "SW1A")
        self.check("Send it to V5K 0A1.", "POSTCODE", "V5K")
        self.check("We are at 14 Elm Street now.", "ADDRESS", "Elm Street")

    def test_names_from_source_metadata(self) -> None:
        self.check("Priya says the draft was wrong. Raman agreed.", "NAME", "Priya", known=("Priya Raman",))
        out, _ = redact.redact("Priya says the draft was wrong. Raman agreed.", ("Priya Raman",))
        self.assertNotIn("Raman", out)

    def test_names_from_phrasing(self) -> None:
        self.check("Hi, my name is Tom Okafor and the chaser is wrong.", "NAME", "Okafor")
        self.check("Hi, this is Sam Whitfield from the joinery.", "NAME", "Whitfield")
        self.check("Spoke with Nadia Brennan about quotes.", "NAME", "Brennan")
        self.check("Dr Ahmed Siddiqui called.", "NAME", "Siddiqui")
        self.check("The quote is wrong.\n\nThanks,\nPriya Raman", "NAME", "Priya")
        self.check("The quote is wrong.\nCheers Grace", "NAME", "Grace")


class RedactKeepsData(unittest.TestCase):
    def test_ordinary_text_unchanged(self) -> None:
        text = "Invoice INV-20431 for 2026-11-12 was 1,240.50 and the quote had 12 line items. This is urgent."
        out, counts = redact.redact(text)
        self.assertEqual(out, text)
        self.assertEqual(sum(counts.values()), 0)

    def test_non_luhn_number_kept(self) -> None:
        out, counts = redact.redact("Order 1234 5678 9012 3456 shipped.")
        self.assertEqual(counts["CARD"], 0)
        self.assertIn("1234 5678 9012 3456", out)

    def test_this_is_not_always_a_name(self) -> None:
        out, _ = redact.redact("This is The worst week. This is Urgent.")
        self.assertNotIn("[NAME]", out)


class Fingerprints(unittest.TestCase):
    def test_known_names_found_without_storing_them(self) -> None:
        prints = redact.fingerprints(["Priya Raman", "tom@okafor.example"], "salt")
        self.assertFalse(any("Priya" in p for p in prints))
        self.assertIn("Priya", redact.fingerprint_hits("Ask Priya about it.", "salt", prints))
        self.assertIn("Priya Raman", redact.fingerprint_hits("Ask Priya Raman about it.", "salt", prints))
        self.assertEqual(redact.fingerprint_hits("Ask the team about it.", "salt", prints), [])

    def test_mask_never_repeats_the_value(self) -> None:
        self.assertNotIn("riya", redact.mask("Priya"))


if __name__ == "__main__":
    unittest.main()
