"""
extract_content.py
------------------
Turns the live Eds Hair pages into clean, structured JSON that the site
generator consumes — so the rebuild uses 100% real content (real services,
real prices, real hours, real NAP, real reviews) rather than placeholder copy.

The Service Menu is a Word-authored set of HTML <table>s. We parse them
structurally rather than by stripping tags, because the flattened text order
interleaves section headings, length labels and price cells ambiguously.

Fixes cp1252 mojibake where the pound sign (0x93) landed as U+FFFD.

Run:  python extract_content.py
"""

from __future__ import annotations

import html
import json
import re
import sys
from html.parser import HTMLParser
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).parent
ANALYSIS = ROOT / "analysis"
OUT = ROOT / "content" / "content.json"

MOJIBAKE = {
    "\ufffd": "\u00a3",
    "\u0093": "\u00a3",
    "\u0096": "\u2013",
    "\u0097": "\u2014",
    "\u0092": "\u2019",
}

TIERS = ["apprentice", "graduate", "stylist", "creative_director"]

# Heading text -> display name. Matching uses the LONGEST matching prefix,
# so "COLOUR REMOVAL" is not swallowed by "COLOUR".
SECTIONS = {
    "BRAZILIAN BLOW DRY": "Brazilian Blow Dry",
    "HAIR BOTOX TREATMENT": "Hair Botox Treatment",
    "HIGHLIGHTS & LOWLIGHTS": "Highlights & Lowlights",
    "BALAYAGE HIGHLIGHTS": "Balayage Highlights",
    "COLOUR REMOVAL": "Colour Removal",
    "CREATIVE COLOUR": "Creative Colour",
    "CHILDREN": "Children (under 12)",
    "CUTTING": "Cutting",
    "STYLING": "Styling",
    "COLOUR": "Colour",
    "PERM & RELAXER": "Perms & Relaxers",
    "TUTORIALS": "Tutorials",
    "SCHWARZKOPF PROFESSIONAL": "Treatments & Add-ons",
}

# Sort keys longest-first so the longest prefix wins.
SECTION_KEYS = sorted(SECTIONS, key=len, reverse=True)

H2_SECTION = {
    "Keratin Smoothing Treatments": "Keratin Smoothing Treatments",
    "Styling Services": "Styling Services",
    "Technical Service": "Technical Service",
    "Tutorials": "Tutorials",
    "Treatments & Add-On's": "Treatments & Add-ons",
}

NA = "Not Available"
CONSULT = "Price on Consultation Only"
PRICE_RE = re.compile(r"^\u00a3(\d+(?:\.\d{2})?)$")


def decode(raw: bytes) -> str:
    text = raw.decode("utf-8", "replace")
    for bad, good in MOJIBAKE.items():
        text = text.replace(bad, good)
    return text


class TableGrab(HTMLParser):
    """Collect every <table> as a list of rows of cell text."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.tables: list[list[list[str]]] = []
        self._t = self._r = self._c = None

    def handle_starttag(self, tag, attrs):
        if tag == "table":
            self._t = []
            self.tables.append(self._t)
        elif tag == "tr" and self._t is not None:
            self._r = []
            self._t.append(self._r)
        elif tag in ("td", "th") and self._r is not None:
            self._c = []

    def handle_endtag(self, tag):
        if tag in ("td", "th") and self._c is not None:
            self._r.append(re.sub(r"\s+", " ", "".join(self._c)).strip())
            self._c = None
        elif tag == "table":
            self._t = None

    def handle_data(self, data):
        if self._c is not None:
            self._c.append(data)


def clean_label(v: str) -> str:
    """Strip the decorative bullet/nbsp characters the Word editor leaves."""
    return re.sub(r"[\u00a0\u2022\u00b7\u25cf\u25aa\u25e6\u2023]+", " ", v).strip()


def norm_key(v: str) -> str:
    """
    Normalise a heading for matching: lowercase, alphanumerics only.

    The source mixes straight and curly apostrophes ("Add-On's" vs
    "Add-On’s"), so we compare on a punctuation-free form.
    """
    return re.sub(r"[^a-z0-9]+", "", v.lower())


H2_LOOKUP = {norm_key(k): v for k, v in H2_SECTION.items()}


def parse_service_menu(html_text: str) -> dict:
    """
    Parse the Service Menu into {section: [rows]}.

    The page is a Word-authored document. Its structure is:
      h2 "Keratin Smoothing Treatments:" -> tables whose first row names a
                                            section (BRAZILIAN BLOW DRY, ...)
      h2 "Styling Services:"             -> table whose rows name sections
      h2 "Technical Service:"            -> tables naming sections + a
                                            Perm/Relaxer table with no heading
      h2 "Treatments & Add-On's:"        -> a two-column add-ons table
      h2 "Tutorials:"                    -> tier table + a two-row table

    So we walk the document in order, tracking the active h2 as a fallback
    section, and let row-level headings override it.
    """
    grab = TableGrab()
    grab.feed(html_text)

    # Map each table to the last h2 that precedes it in the source.
    h2_positions = []
    for m in re.finditer(r"(?is)<h2[^>]*>(.*?)</h2>", html_text):
        label = clean_label(html.unescape(re.sub(r"<[^>]+>", " ", m.group(1))))
        h2_positions.append((m.start(), label.rstrip(":").strip()))
    table_positions = [m.start() for m in re.finditer(r"<table[^>]*>", html_text)]

    def h2_before(pos: int) -> str:
        active = ""
        for hp, label in h2_positions:
            if hp < pos:
                active = label
            else:
                break
        return active

    services: dict[str, list[dict]] = {}
    addons: list[dict] = []

    # h2 -> section name used when a table carries no row-level heading.
    H2_LOOKUP_LOCAL = H2_LOOKUP

    def price_value(v: str):
        if v in (NA, "N/A", ""):
            return None
        if v == CONSULT:
            return "consult"
        m = PRICE_RE.match(v)
        return float(m.group(1)) if m else None

    for t_idx, tbl in enumerate(grab.tables):
        active_h2 = h2_before(table_positions[t_idx]) if t_idx < len(table_positions) else ""
        h2_section = H2_LOOKUP.get(norm_key(active_h2))

        # Each table resolves its own section: row-level headings win, and the
        # enclosing h2 is only a fallback.
        section = None
        group = None
        pending = None

        for row in tbl:
            cells = list(row)
            if not cells:
                continue
            label = clean_label(cells[0])
            rest = cells[1:]

            # Tier-header row: ['', 'Apprentice', 'Graduate Stylist', ...]
            if not label and any(
                x.upper() in ("APPRENTICE", "GRADUEE STYLIST", "STYLIST", "CREATIVE DIRECTOR")
                for x in rest
            ):
                continue
            if not label and not rest:
                continue

            upper = label.upper()

            # Perm / Relaxer rows have no heading of their own in the source
            # document (they sit under the add-ons heading), so route them by
            # name before any other table-specific handling.
            if upper.startswith("PERM") or upper.startswith("RELAXER"):
                if len(rest) == 4:
                    rec = {"name": label}
                    for k, tier in enumerate(TIERS):
                        rec[tier] = price_value(rest[k])
                    services.setdefault("Perms & Relaxers", []).append(rec)
                continue

            # The two-column "Treatments & Add-ons" table. A row is either
            # [name, price] or [name1, price1, name2, price2] — two products
            # per row — so `rest` holds [price1, name2, price2].
            if h2_section == "Treatments & Add-ons":
                if rest and PRICE_RE.match(rest[0]):
                    addons.append({"name": label, "price": price_value(rest[0])})
                    if len(rest) >= 3 and rest[1] and PRICE_RE.match(rest[2]):
                        addons.append({
                            "name": clean_label(rest[1]),
                            "price": price_value(rest[2]),
                        })
                elif not label and len(rest) >= 3 and rest[1] and PRICE_RE.match(rest[2]):
                    # Continuation row: the first cell is empty, the second
                    # product is in the right-hand columns.
                    addons.append({
                        "name": clean_label(rest[1]),
                        "price": price_value(rest[2]),
                    })
                continue

            # A heading row: only the label is populated, all price cells empty.
            if not any(rest):
                matched = None
                for raw_key in SECTION_KEYS:
                    if upper.startswith(raw_key):
                        matched = SECTIONS[raw_key]
                        break
                if matched:
                    section = matched
                    group = None
                    services.setdefault(section, [])
                    continue
                if section is not None:
                    # Sub-group header inside the current section.
                    group = label
                    pending = None
                    continue
                continue

            # A row of 4 prices.
            if len(rest) == 4:
                if section is None:
                    section = h2_section or "Services"
                    services.setdefault(section, [])

                rec = {"name": label}
                if group:
                    rec["group"] = group
                if pending:
                    rec["length"] = pending
                    pending = None
                for k, tier in enumerate(TIERS):
                    rec[tier] = price_value(rest[k])

                # Perm / Relaxer rows sit under "Technical Service" with no
                # heading of their own — give them a named section.
                target_section = section
                if section == "Technical Service" and (
                    upper.startswith("PERM") or upper.startswith("RELAXER")
                ):
                    target_section = "Perms & Relaxers"
                services.setdefault(target_section, []).append(rec)
                continue

            # A length row whose prices sit on a following row (e.g. "Below Waist").
            if len(rest) == 1 and rest[0] in (NA, CONSULT, "N/A"):
                pending = label
                continue

    cleaned: dict[str, list[dict]] = {}
    for name, rows in services.items():
        real = [r for r in rows if r.get("name")]
        if real:
            cleaned[name] = real
    return cleaned, addons


def extract_reviews(html_text: str, limit: int = 6) -> list[dict]:
    """Pull the real testimonial quotes out of the homepage carousel."""
    i = html_text.find("testimonial-section")
    if i == -1:
        return []
    seg = html_text[i:i + 16000]
    seg = re.sub(r"(?s)<script.*?</script>", "", seg)
    seg = re.sub(r"(?s)<style.*?</style>", "", seg)

    # Each testimonial slide: <h2>title</h2> <div class="description"><p>quote</p>
    # </div> <p><strong>— Name</strong></p>
    pattern = re.compile(
        r"(?is)<h[2-6][^>]*>(.*?)</h[2-6]>.*?"
        r'<div[^>]*class="[^"]*description[^"]*"[^>]*>\s*<p[^>]*>(.*?)</p>.*?'
        r"<p[^>]*>\s*<strong[^>]*>(.*?)</strong>"
    )
    reviews = []
    for title, quote, who in pattern.findall(seg):
        t = clean_label(html.unescape(re.sub(r"<[^>]+>", " ", title)))
        q = clean_label(html.unescape(re.sub(r"<[^>]+>", " ", quote)))
        w = clean_label(html.unescape(re.sub(r"<[^>]+>", " ", who)))
        w = re.sub(r"^[\u2014\u2013-]\s*", "", w).strip()
        if len(q) < 25:
            continue
        if any(x in q.lower() for x in ("rePete", "loyalty", "reward", "javascript")):
            continue
        service = ""
        if " - " in t:
            service = t.split(" - ", 1)[1].strip()
        reviews.append({"quote": q, "name": w, "service": service})
        if len(reviews) >= limit:
            break
    return reviews


def main() -> None:
    services_html = decode((ANALYSIS / "services.html").read_bytes())
    parsed, addons = parse_service_menu(services_html)
    out: dict = {"services": parsed, "addons": addons}

    out["hours"] = [
        {"day": "Monday", "open": "8:30", "close": "16:00"},
        {"day": "Tuesday", "open": "8:30", "close": "17:30"},
        {"day": "Wednesday", "open": "8:30", "close": "19:00"},
        {"day": "Thursday", "open": "8:30", "close": "19:00"},
        {"day": "Friday", "open": "8:30", "close": "17:30"},
        {"day": "Saturday", "open": "8:30", "close": "16:00"},
        {"day": "Sunday", "open": None, "close": None},
    ]

    out["nap"] = {
        "name": "Eds Hair",
        "street": "13 Bramhall Lane South",
        "locality": "Bramhall",
        "region": "Cheshire",
        "postalCode": "SK7 1AL",
        "country": "GB",
        "countryName": "United Kingdom",
        "phone": "0161 439 8058",
        "phoneE164": "+441614398058",
        "bookingUrl": "https://phorest.com/book/salons/edshair",
        "appUrl": "https://bit.ly/EdsBramhall",
        "giftUrl": "https://gift-cards.phorest.com/salons/edshair",
        "facebook": "https://www.facebook.com/EdsHairBramhall/",
        "instagram": "https://www.instagram.com/EdsHairBramhall/",
        "priceListPdf": "https://cdn.shopify.com/s/files/1/2112/9277/files/Eds_Price_List_20260901.pdf?v=1787594039",
    }
    out["tagline"] = "Luxe hair specialists in Bramhall, Stockport"
    out["slogan"] = "We exist to create happiness"
    out["credentials"] = [
        "Schwarzkopf Professional Colour Master",
        "Ambassadors for Glowwa",
        "Schwarzkopf Collective Team",
    ]
    out["specialities"] = [
        "Balayage & lived-in colour",
        "Brazilian blow dries",
        "Keratin smoothing",
        "Hair Botox treatments",
    ]
    out["notices"] = [
        "We are closed for Bank Holidays.",
        "A skin test is required at least 48 hours before all colour and "
        "highlighting services and must be renewed annually.",
        "Additional charges may apply for long or thick hair. A \u00a320 surcharge "
        "applies to the formaldehyde-free Brazilian Blow Dry.",
        "We kindly request a minimum of 48 hours' notice for appointment "
        "cancellations or amendments.",
        "Customer consultations and Colour Passports are both charged at \u00a315.",
    ]
    out["directions"] = (
        "Located 5 minutes from the A34 between Cheadle and Wilmslow on the "
        "perimeter of the Bramhall Shopping Centre. There is a public car park "
        "behind us (near Sainsbury's) that is 20p per hour. Bramhall is also "
        "served well by Stagecoach bus 378 and by train from Manchester Piccadilly."
    )

    home = decode((ANALYSIS / "live.html").read_bytes())
    out["reviews"] = extract_reviews(home)

    all_html = decode((ANALYSIS / "collections_all.html").read_bytes())
    names: list[str] = []
    for m in re.finditer(r'"title":"([^"]{4,90})"', all_html):
        nm = m.group(1)
        if nm in names or nm.startswith("http") or nm.lower() in ("default title", "title"):
            continue
        names.append(nm)
    out["productNames"] = names[:80]

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")

    total = sum(len(v) for v in out["services"].values())
    print(f"sections: {len(out['services'])}   rows: {total}   add-ons: {len(addons)}")
    for s, rows in out["services"].items():
        print(f"  {s:26} {len(rows):>2} rows")
    print(f"reviews: {len(out['reviews'])}   product names: {len(out['productNames'])}")
    print(f"-> {OUT}")


if __name__ == "__main__":
    main()
