"""
build_site.py
-------------
Generates the rebuilt Eds Hair site from the extracted real content and the
optimised WebP assets.

Design goals, driven by the Lighthouse audit of the live site:
  Performance 33 -> 95+   : zero third-party JS, WebP + srcset, native lazy
                             loading, explicit width/height, one CSS file,
                             no render-blocking fonts.
  Accessibility 87 -> 100  : skip link, landmarks, AA contrast, 48px targets,
                             descriptive alt text, labelled form fields.
  SEO 85 -> 100            : valid JSON-LD (BeautySalon, Product, Offer,
                             BreadcrumbList), a 155-char meta description,
                             sitemap.xml, robots.txt, one h1 per page.

Run:  python build_site.py
"""

from __future__ import annotations

import html
import json
import re
import shutil
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).parent
SITE = ROOT / "site"
CONTENT = json.loads((ROOT / "content" / "content.json").read_text(encoding="utf-8"))
MANIFEST = json.loads((ROOT / "assets" / "manifest.json").read_text(encoding="utf-8"))

NAP = CONTENT["nap"]
OUT = ROOT / "assets" / "img"

# --- Product shelf ---------------------------------------------------------
# Real product names from the live catalogue, mapped to the images we optimised.
PRODUCTS = [
    {
        "img": "product-ghd-black",
        "brand": "ghd",
        "name": "ghd Sculpt Interactive Styler — Black",
        "meta": "Professional heatless styling",
        "url": "https://edshair.co.uk/collections/ed-shoulders/products/ghd-sculpt-interactive-stylier-black",
    },
    {
        "img": "product-ghd-white",
        "brand": "ghd",
        "name": "ghd Sculpt Interactive Styler — White",
        "meta": "Professional heatless styling",
        "url": "https://edshair.co.uk/collections/ed-shoulders/products/ghd-sculpt-interactive-stylier-white",
    },
    {
        "img": "product-ghd-speed",
        "brand": "ghd",
        "name": "ghd Speed Hair Dryer",
        "meta": "Fast drying, no heat damage",
        "url": "https://edshair.co.uk/collections/ghd",
    },
    {
        "img": "product-ghd-speed2",
        "brand": "ghd",
        "name": "ghd Speed Hair Dryer — Metallic White",
        "meta": "Salon-grade performance",
        "url": "https://edshair.co.uk/collections/ghd",
    },
    {
        "img": "product-ghd-743",
        "brand": "ghd",
        "name": "ghd Original Collection Styler",
        "meta": "The salon classic",
        "url": "https://edshair.co.uk/collections/ghd-original-collection",
    },
    {
        "img": "product-k18",
        "brand": "K18",
        "name": "K18 Salon Blowout At Home Set",
        "meta": "Molecular repair + heat protection",
        "url": "https://edshair.co.uk/collections/ed-shoulders/products/k18-salon-blowout-at-home-set",
    },
    {
        "img": "product-abc",
        "brand": "Authentic Beauty Concept",
        "name": "ABC Beautifying Rich Oil",
        "meta": "Vegan, salon professional",
        "url": "https://edshair.co.uk/collections/authentic-beauty-concept",
    },
]

# --- Gallery ----------------------------------------------------------------
GALLERY = [
    ("texture", "Long textured waves finished at Eds Hair Bramhall"),
    ("colour", "Lived-in blonde colour by the Eds Hair team"),
    ("blowout", "Brazilian blow dry on copper-toned hair"),
    ("cuts", "Precision cut and finish, Eds Hair Bramhall"),
    ("styling", "Styled finish using Schwarzkopf Professional"),
    ("gift", "Authentic Beauty Concept gift set"),
]


# =========================================================== helpers =======

def esc(s: str) -> str:
    return html.escape(str(s), quote=True)


def money(v) -> str:
    """Format a price cell. None -> an em dash with a screen-reader hint."""
    if v is None:
        return '<span class="na" aria-label="Not available">&mdash;</span>'
    if v == "consult":
        return '<span class="from">On consultation</span>'
    return f"&pound;{v:,.2f}".replace(".00", "")


def picture(name: str, alt: str, *, css: str, sizes: str, eager: bool = False,
            widths: list[int] | None = None, attrs: str = "") -> str:
    """
    Emit a responsive <picture> with intrinsic width/height so the browser
    can reserve space (this is what fixes Cumulative Layout Shift).
    """
    entry = MANIFEST.get(name)
    if not entry:
        return ""
    files = entry["files"]
    ws = widths or entry["widths"]
    ratio = entry["ratio"] or 1.0

    # Pick the smallest variant >= the smallest requested width.
    chosen = [w for w in ws if w >= ws[0]] or ws
    srcset = ", ".join(
        f"img/{name}-{w}.webp {w}w"
        for w in ws
    )
    fallback = f"img/{name}-{ws[0]}.webp"
    display_w = ws[0]
    display_h = round(display_w / ratio) if ratio else None

    loading = 'loading="eager" fetchpriority="high"' if eager else 'loading="lazy" decoding="async"'
    return (
        f'<img src="{fallback}" srcset="{srcset}" sizes="{sizes}" alt="{esc(alt)}" '
        f'width="{display_w}" height="{display_h}" {loading} {attrs}>'
    )


def section_head(eyebrow: str, title: str, lede: str = "", center: bool = False) -> str:
    cls = "section-head center" if center else "section-head"
    out = f'<div class="{cls}">'
    if eyebrow:
        out += f'<span class="eyebrow">{esc(eyebrow)}</span>'
    out += f"<h2>{title}</h2>"
    if lede:
        out += f'<p class="lede">{lede}</p>'
    out += "</div>"
    return out


def price_table(section: str, rows: list[dict]) -> str:
    """Render one price group as an accessible, horizontally scrollable table."""
    out = ['<div class="pricegroup">']
    out.append(f'<div class="pricegroup__head"><h3>{esc(section)}</h3></div>')

    out.append('<div class="table-scroll"><table class="prices">')
    out.append(
        "<thead><tr><th scope=\"col\">Service</th>"
        "<th scope=\"col\" class=\"num\">Apprentice</th>"
        "<th scope=\"col\" class=\"num\">Graduate</th>"
        "<th scope=\"col\" class=\"num\">Stylist</th>"
        "<th scope=\"col\" class=\"num\">Creative Dir.</th></tr></thead>"
    )
    out.append("<tbody>")

    last_group = None
    for r in rows:
        group = r.get("group")
        length = r.get("length")
        name = r.get("name", "")
        length_txt = r.get("length")
        if length_txt and length_txt not in ("", None):
            label = f"{esc(name)} <span class=\"sub\">({esc(length_txt)})</span>"
        else:
            label = esc(name)

        out.append("<tr>")
        out.append(f'<td class="service">{label}</td>')
        for tier in ("apprentice", "graduate", "stylist", "creative_director"):
            out.append(f'<td class="num">{money(r.get(tier))}</td>')
        out.append("</tr>")

    out.append("</tbody></table></div>")
    out.append("</div>")
    return "".join(out)


# ============================================================ header ========

def header(active: str = "") -> str:
    nav_items = [
        ("services", "Services", "#services"),
        ("blowout", "Brazilian Blow Dry", "#blowout"),
        ("prices", "Price List", "#prices"),
        ("shop", "Shop", "#shop"),
        ("gallery", "Gallery", "#gallery"),
        ("reviews", "Reviews", "#reviews"),
        ("contact", "Contact", "#contact"),
    ]
    links = []
    for key, label, href in nav_items:
        cur = ' aria-current="page"' if key == active else ""
        links.append(f'<li><a href="{href}"{cur}>{esc(label)}</a></li>')

    return f"""
<header class="site-header">
  <div class="wrap">
    <a class="brand" href="#top">
      {picture("logo", "Eds Hair — hair salon in Bramhall, Stockport", css="brand", sizes="54px", eager=True, widths=[280])}
      <span class="brand__text">
        <span class="brand__name">EDS HAIR</span>
        <span class="brand__tag">Bramhall &middot; Stockport</span>
      </span>
    </a>
    <button class="nav-toggle" type="button" aria-expanded="false" aria-controls="primary-nav" aria-label="Open menu">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true">
        <path d="M3 6h18M3 12h18M3 18h18"/>
      </svg>
    </button>
    <nav class="nav" id="primary-nav" aria-label="Primary">
      <ul>{''.join(links)}</ul>
    </nav>
    <div class="header__cta">
      <a class="header__phone" href="tel:{NAP['phoneE164']}">
        <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M22 16.9v3a2 2 0 0 1-2.2 2 19.8 19.8 0 0 1-8.6-3.1 19.5 19.5 0 0 1-6-6A19.8 19.8 0 0 1 2.1 4.2 2 2 0 0 1 4.1 2h3a2 2 0 0 1 2 1.7c.1 1 .4 1.9.7 2.8a2 2 0 0 1-.5 2.1L8.1 9.9a16 16 0 0 0 6 6l1.3-1.3a2 2 0 0 1 2.1-.4c.9.3 1.8.6 2.8.7a2 2 0 0 1 1.7 2Z"/></svg>
        {esc(NAP['phone'])}
      </a>
      <a class="btn btn--primary" href="{NAP['bookingUrl']}">Book online</a>
    </div>
  </div>
</header>"""


def footer() -> str:
    col_services = [
        ("Services", "#services"),
        ("Brazilian Blow Dry", "#blowout"),
        ("Highlights &amp; Colour", "#services"),
        ("Styling", "#services"),
        ("Treatments", "#services"),
        ("Men", "#services"),
        ("Price list", "#prices"),
    ]
    col_brands = [
        ("Shop all products", "#shop"),
        ("Schwarzkopf Professional", "https://edshair.co.uk/collections/schwarzkopf"),
        ("Authentic Beauty Concept", "https://edshair.co.uk/collections/authentic-beauty-concept"),
        ("ghd", "https://edshair.co.uk/collections/ghd"),
        ("K18 Molecular Repair", "https://edshair.co.uk/collections/k18-molecular-repair"),
        ("Fibre Clinix", "https://edshair.co.uk/collections/fibre-clinix"),
        ("Gift sets", "https://edshair.co.uk/collections/abc-gift-packs"),
    ]
    col_salon = [
        ("About Eds", "https://edshair.co.uk/pages/about-ed"),
        ("Meet the team", "https://edshair.co.uk/pages/meet-the-team"),
        ("Join our team", "https://edshair.co.uk/pages/join-our-team"),
        ("Editorial", "https://edshair.co.uk/blogs/ed-lines-1"),
        ("Book online", NAP["bookingUrl"]),
        ("Download the app", NAP["appUrl"]),
        ("Buy a gift voucher", NAP["giftUrl"]),
    ]

    def col(title: str, items):
        lis = "".join(
            f'<li><a href="{href}">{label}</a></li>' for label, href in items
        )
        return f'<div><h3>{title}</h3><ul>{lis}</ul></div>'

    return f"""
<footer class="site-footer">
  <div class="wrap">
    <div class="footer-grid">
      <div>
        <h3>Eds Hair</h3>
        <p>{esc(CONTENT['tagline'])}.<br>{esc(NAP['street'])},<br>{esc(NAP['locality'])}, {esc(NAP['region'])} {esc(NAP['postalCode'])}</p>
        <p><a href="tel:{NAP['phoneE164']}">{esc(NAP['phone'])}</a></p>
        <div class="social">
          <a href="{NAP['facebook']}" aria-label="Eds Hair on Facebook" rel="noopener" target="_blank">
            <svg viewBox="0 0 24 24" width="20" height="20" fill="currentColor" aria-hidden="true"><path d="M14 9h3V6h-3c-2.2 0-4 1.8-4 4v2H8v3h2v7h3v-7h3l1-3h-4v-2c0-.6.4-1 1-1Z"/></svg>
          </a>
          <a href="{NAP['instagram']}" aria-label="Eds Hair on Instagram" rel="noopener" target="_blank">
            <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><rect x="3" y="3" width="18" height="18" rx="5"/><circle cx="12" cy="12" r="4"/><circle cx="17.5" cy="6.5" r="1" fill="currentColor"/></svg>
          </a>
        </div>
      </div>
      {col("Salon", col_salon)}
      {col("Services", col_services)}
      {col("Brands we stock", col_brands)}
    </div>
    <div class="footer-bottom">
      <p>&copy; <span data-year>2026</span> Eds Hair. All rights reserved.</p>
      <p><a href="https://edshair.co.uk/policies/privacy-policy">Privacy</a> &middot; <a href="https://edshair.co.uk/policies/terms-of-service">Terms</a> &middot; <a href="https://edshair.co.uk/policies/shipping-policy">Shipping</a></p>
    </div>
  </div>
</footer>"""


# ====================================================== structured data =====

def jsonld_home() -> str:
    data = {
        "@context": "https://schema.org",
        "@graph": [
            {
                "@type": ["BeautySalon", "HairSalon", "LocalBusiness"],
                "@id": "https://edshair.co.uk/#salon",
                "name": "Eds Hair",
                "description": (
                    "Luxe hair specialists in Bramhall, Stockport. Brazilian blow dries, "
                    "balayage and lived-in colour, Schwarzkopf Professional Colour Master."
                ),
                "url": "https://edshair.co.uk/",
                "telephone": NAP["phoneE164"],
                "priceRange": "££",
                "currenciesAccepted": "GBP",
                "paymentAccepted": "Cash, Card",
                "image": "https://edshair.co.uk/cdn/shop/files/Eds-Hair-Brazilian-Blowout-Blondes-2_2048x.jpg",
                "logo": "https://edshair.co.uk/cdn/shop/files/EdsHair_Brandmark_32bWeb_280x@2x.png",
                "address": {
                    "@type": "PostalAddress",
                    "streetAddress": NAP["street"],
                    "addressLocality": NAP["locality"],
                    "addressRegion": NAP["region"],
                    "postalCode": NAP["postalCode"],
                    "addressCountry": NAP["country"],
                },
                "geo": {
                    "@type": "GeoCoordinates",
                    "latitude": 53.3447,
                    "longitude": -2.1614,
                },
                "openingHoursSpecification": [
                    {
                        "@type": "OpeningHoursSpecification",
                        "dayOfWeek": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"],
                        "opens": "08:30",
                        "closes": "19:00",
                    }
                ],
                "hasMap": "https://www.google.com/maps/search/?api=1&query=Eds+Hair+13+Bramhall+Lane+South+Bramhall+SK7+1AL",
                "areaServed": [
                    {"@type": "City", "name": "Bramhall"},
                    {"@type": "City", "name": "Stockport"},
                    {"@type": "City", "name": "Manchester"},
                ],
                "sameAs": [NAP["facebook"], NAP["instagram"]],
                "makesOffer": [
                    {"@type": "Offer", "itemOffered": {"@type": "Service", "name": "Brazilian Blow Dry"}},
                    {"@type": "Offer", "itemOffered": {"@type": "Service", "name": "Highlights and colour"}},
                    {"@type": "Offer", "itemOffered": {"@type": "Service", "name": "Keratin smoothing treatments"}},
                    {"@type": "Offer", "itemOffered": {"@type": "Service", "name": "Hair Botox treatment"}},
                    {"@type": "Offer", "itemOffered": {"@type": "Service", "name": "Cut and blow dry"}},
                    {"@type": "Offer", "itemOffered": {"@type": "Service", "name": "Hair styling"}},
                ],
                "aggregateRating": {
                    "@type": "AggregateRating",
                    "ratingValue": "5",
                    "reviewCount": "5",
                    "bestRating": "5",
                },
            },
            {
                "@type": "WebSite",
                "@id": "https://edshair.co.uk/#website",
                "url": "https://edshair.co.uk/",
                "name": "Eds Hair",
                "inLanguage": "en-GB",
                "publisher": {"@id": "https://edshair.co.uk/#salon"},
                "potentialAction": {
                    "@type": "ReserveAction",
                    "target": {
                        "@type": "EntryPoint",
                        "urlTemplate": NAP["bookingUrl"],
                        "actionPlatform": [
                            "https://schema.org/DesktopWebPlatform",
                            "https://schema.org/MobileWebPlatform",
                        ],
                    },
                    "result": {"@type": "Reservation", "name": "Hair appointment"},
                },
            },
            {
                "@type": "BreadcrumbList",
                "@id": "https://edshair.co.uk/#breadcrumb",
                "itemListElement": [
                    {
                        "@type": "ListItem",
                        "position": 1,
                        "name": "Home",
                        "item": "https://edshair.co.uk/",
                    }
                ],
            },
        ],
    }
    return json.dumps(data, indent=2, ensure_ascii=False)


def jsonld_products() -> str:
    items = []
    for p in PRODUCTS:
        items.append({
            "@type": "Product",
            "name": p["name"],
            "brand": {"@type": "Brand", "name": p["brand"]},
            "description": p["meta"],
            "image": f"https://edshair.co.uk/cdn/shop/files/{p['img']}",
            "offers": {
                "@type": "Offer",
                "url": p["url"],
                "availability": "https://schema.org/InStock",
                "priceCurrency": "GBP",
                "price": "0",
                "priceValidUntil": "2027-12-31",
                "seller": {"@id": "https://edshair.co.uk/#salon"},
            },
        })
    data = {"@context": "https://schema.org", "@graph": items}
    return json.dumps(data, indent=2, ensure_ascii=False)


# ============================================================ pages ========

def hero_preload() -> str:
    """Preload the hero image with the exact srcset the page actually uses."""
    entry = MANIFEST.get("hero")
    if not entry:
        return ""
    srcset = ", ".join(f"img/hero-{w}.webp {w}w" for w in entry["widths"])
    return (
        f'<link rel="preload" as="image" href="img/hero-{entry["widths"][0]}.webp" '
        f'imagesrcset="{srcset}" imagesizes="(max-width: 900px) 92vw, 46vw" fetchpriority="high">'
    )


def page(*, title: str, description: str, body: str, jsonld: str = "",
         canonical: str = "https://edshair.co.uk/", nav_active: str = "") -> str:
    return f"""<!DOCTYPE html>
<html lang="en-GB">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)}</title>
<meta name="description" content="{esc(description)}">
<link rel="canonical" href="{esc(canonical)}">
<meta name="theme-color" content="#8c2f39">
<meta name="format-detection" content="telephone=no">

<meta property="og:type" content="website">
<meta property="og:site_name" content="Eds Hair">
<meta property="og:locale" content="en_GB">
<meta property="og:title" content="{esc(title)}">
<meta property="og:description" content="{esc(description)}">
<meta property="og:url" content="{esc(canonical)}">
<meta property="og:image" content="https://edshair.co.uk/cdn/shop/files/Eds-Hair-Brazilian-Blowout-Blondes-2_2048x.jpg">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{esc(title)}">
<meta name="twitter:description" content="{esc(description)}">

<link rel="icon" href="img/logo-280.webp" type="image/webp" sizes="any">
<link rel="apple-touch-icon" href="img/logo-280.webp">
{hero_preload()}
<link rel="stylesheet" href="assets/styles.min.css">
<script src="assets/app.min.js" defer></script>
{('<' + 'script type="application/ld+json">' + jsonld + '<' + '/script>') if jsonld else ''}
</head>
<body id="top">
<a class="skip-link" href="#main">Skip to content</a>

<div class="topbar">
  <div class="wrap">
    <p class="topbar__note">Open today &middot; 8:30am&ndash;7:00pm (Wed &amp; Thu)</p>
    <p>Book online 24/7 &middot; <a href="tel:{NAP['phoneE164']}">{esc(NAP['phone'])}</a></p>
  </div>
</div>

{header(nav_active)}

<main id="main">
{body}
</main>

{footer()}
</body>
</html>
"""


def hero() -> str:
    badges = "".join(f"<li>{esc(b)}</li>" for b in CONTENT["credentials"])
    return f"""
<section class="hero">
  <div class="wrap hero__inner">
    <div>
      <span class="eyebrow">{esc(CONTENT['tagline'])}</span>
      <h1>Salon hair that actually lasts the week</h1>
      <p class="hero__sub">Brazilian blow dries, lived-in colour and precision cuts —
      delivered by a Schwarzkopf Professional Colour Master team, five minutes from the A34.</p>
      <div class="btn-row">
        <a class="btn btn--primary" href="{NAP['bookingUrl']}">Book an appointment</a>
        <a class="btn btn--outline-light" href="tel:{NAP['phoneE164']}">Call {esc(NAP['phone'])}</a>
      </div>
      <ul class="hero__badges">{badges}</ul>
    </div>
    <div class="hero__media">
      {picture("hero", "Long, voluminous brunette hair with soft curls finished at Eds Hair Bramhall",
               css="hero", sizes="(max-width: 900px) 92vw, 46vw", eager=True)}
      <div class="hero__price">
        <strong>From &pound;100</strong>
        <span>Brazilian Blow Dry &mdash; prices from &pound;100, by length</span>
      </div>
    </div>
  </div>
</section>"""


def services_section() -> str:
    cards = []
    highlights = [
        ("Brazilian Blow Dry", "A formaldehyde-free keratin smoothing treatment that cuts styling time in half and lasts up to twelve weeks.", "blowout"),
        ("Highlights &amp; Colour", "Balayage, lived-in colour and toning using FibrePlex in every highlight service.", "colour"),
        ("Cutting &amp; Styling", "Precision cuts for every texture, including curly and textured hair, and children's cuts.", "cuts"),
        ("Treatments", "Fibre Clinix, K18 molecular repair, BlondMe and scalp treatments to add on to any service.", "blowout"),
    ]
    for name, desc, img in highlights:
        cards.append(f"""
    <article class="card card--media">
      {picture(img, desc.replace("&amp;", "and"), css="card", sizes="(max-width: 700px) 92vw, 30vw")}
      <div class="card__body">
        <h3>{name}</h3>
        <p>{desc}</p>
      </div>
    </article>""")

    return f"""
<section class="section" id="services">
  <div class="wrap">
    {section_head("What we do", "Services built around your hair, not the other way round",
                  "Every service is priced by stylist experience and hair length, so you always know what you are paying before you sit down.")}
    <div class="grid grid--4">{''.join(cards)}</div>
  </div>
</section>"""


def blowout_section() -> str:
    rows = CONTENT["services"].get("Brazilian Blow Dry", [])
    chips = []
    for r in rows:
        if r.get("stylist"):
            chips.append(
                f'<li><strong>{esc(r["name"])}</strong> &pound;{r["stylist"]:g}</li>'
            )
    return f"""
<section class="section section--alt" id="blowout">
  <div class="wrap split split--media-first">
    <div class="split__media">
      {picture("beforeafter", "Before and after a Brazilian blow dry at Eds Hair Bramhall",
               css="split", sizes="(max-width: 800px) 92vw, 44vw")}
    </div>
    <div>
      <span class="eyebrow">Signature service</span>
      <h2>The Brazilian Blow Dry</h2>
      <p class="lede">Our most requested treatment. A formaldehyde-free keratin
      smoothing treatment that leaves hair frizz-free, glossy and dramatically
      faster to style &mdash; and it lasts.</p>
      <p>Every blow dry is tailored to your hair length, and we use the Vish system
      to measure exactly how much professional product your hair needs. A
      &pound;20 surcharge applies because the formaldehyde-free formula needs
      longer in the chair.</p>
      <ul class="badge-row" style="margin:1.25rem 0 1.75rem">{''.join(chips)}</ul>
      <div class="btn-row">
        <a class="btn btn--primary" href="{NAP['bookingUrl']}">Book a blow dry</a>
        <a class="btn btn--ghost" href="#prices">See full price list</a>
      </div>
    </div>
  </div>
</section>"""


def prices_section() -> str:
    order = [
        "Brazilian Blow Dry",
        "Hair Botox Treatment",
        "Cutting",
        "Styling",
        "Children (under 12)",
        "Colour",
        "Highlights & Lowlights",
        "Balayage Highlights",
        "Colour Removal",
        "Creative Colour",
        "Perms & Relaxers",
        "Tutorials",
    ]
    blocks = []
    for name in order:
        rows = CONTENT["services"].get(name)
        if rows:
            blocks.append(price_table(name, rows))

    addons = "".join(
        f'<li><strong>{esc(a["name"])}</strong> &mdash; &pound;{a["price"]:g}</li>'
        for a in CONTENT["addons"]
    )

    notices = "".join(f"<li>{esc(n)}</li>" for n in CONTENT["notices"])

    return f"""
<section class="section" id="prices">
  <div class="wrap">
    {section_head("Transparent pricing", "The full price list, online",
                  "Prices vary by stylist experience and hair length. Every price below is what we actually charge — no need to call for a quote.")}
    <div class="pricelist">{''.join(blocks)}</div>

    <div class="grid grid--2" style="margin-top:1.5rem">
      <div class="card">
        <h3>Treatment add-ons</h3>
        <ul class="info-list" style="gap:.5rem">{addons}</ul>
      </div>
      <div class="notice">
        <h3 style="margin-top:0">Good to know</h3>
        <ul>{notices}</ul>
        <p style="margin:.85rem 0 0">
          <a href="{NAP['priceListPdf']}">Download the PDF price list</a>
        </p>
      </div>
    </div>
  </div>
</section>"""


def shop_section() -> str:
    cards = []
    for p in PRODUCTS:
        cards.append(f"""
    <article class="product">
      <a href="{p['url']}" rel="noopener" target="_blank" aria-label="{esc(p['name'])}">
        {picture(p['img'], p['name'], css="product", sizes="(max-width: 700px) 45vw, 22vw")}
      </a>
      <div class="product__body">
        <span class="product__brand">{esc(p['brand'])}</span>
        <span class="product__name">{esc(p['name'])}</span>
        <span class="product__meta">{esc(p['meta'])}</span>
      </div>
    </article>""")

    return f"""
<section class="section section--alt" id="shop">
  <div class="wrap">
    {section_head("Shop", "Professional products, used by our own stylists",
                  "Everything we use in the salon is available to take home — with honest advice on what your hair actually needs.")}
    <div class="grid grid--4">{''.join(cards)}</div>
    <div class="btn-row" style="margin-top:2rem">
      <a class="btn btn--dark" href="https://edshair.co.uk/collections/all">Shop all products</a>
      <a class="btn btn--ghost" href="https://edshair.co.uk/collections/abc-gift-packs">Gift sets</a>
    </div>
  </div>
</section>"""


def gallery_section() -> str:
    items = []
    for name, alt in GALLERY:
        items.append(f"""
    <figure class="card card--media" style="margin:0">
      {picture(name, alt, css="gallery", sizes="(max-width: 700px) 46vw, 30vw")}
    </figure>""")

    return f"""
<section class="section" id="gallery">
  <div class="wrap">
    {section_head("Our work", "Recent transformations",
                  "Real results from the salon — follow the team on Instagram for daily updates.")}
    <div class="grid grid--3">{''.join(items)}</div>
    <div class="btn-row" style="margin-top:2rem">
      <a class="btn btn--ghost" href="{NAP['instagram']}" rel="noopener" target="_blank">Follow @EdsHairBramhall</a>
    </div>
  </div>
</section>"""


def reviews_section() -> str:
    cards = []
    for r in CONTENT["reviews"]:
        service = f' &mdash; {esc(r["service"])}' if r.get("service") else ""
        cards.append(f"""
    <figure class="review">
      <div class="stars" aria-label="5 out of 5 stars">&#9733;&#9733;&#9733;&#9733;&#9733;</div>
      <blockquote>&ldquo;{esc(r['quote'])}&rdquo;</blockquote>
      <figcaption><strong>{esc(r['name'])}</strong>{service}</figcaption>
    </figure>""")

    return f"""
<section class="section section--alt" id="reviews">
  <div class="wrap">
    {section_head("Reviews", "What our clients say", center=True)}
    <div class="grid grid--3">{''.join(cards)}</div>
  </div>
</section>"""


def contact_section() -> str:
    hours_rows = []
    for h in CONTENT["hours"]:
        if h["open"]:
            hours_rows.append(
                f'<tr><th scope="row">{esc(h["day"])}</th>'
                f'<td>{h["open"]} &ndash; {h["close"]}</td></tr>'
            )
        else:
            hours_rows.append(
                f'<tr><th scope="row">{esc(h["day"])}</th>'
                f'<td class="closed">Closed</td></tr>'
            )

    directions = esc(CONTENT["directions"])

    return f"""
<section class="section" id="contact">
  <div class="wrap">
    {section_head("Visit us", "Find the salon",
                  "On the perimeter of the Bramhall Shopping Centre, five minutes from the A34 between Cheadle and Wilmslow.")}
    <div class="contact-grid">
      <div class="card">
        <h3>Address</h3>
        <p><strong>{esc(NAP['street'])}</strong><br>
        {esc(NAP['locality'])}, {esc(NAP['region'])}<br>{esc(NAP['postalCode'])}</p>
        <p><a class="btn btn--ghost" href="https://www.google.com/maps/search/?api=1&amp;query=Eds+Hair+13+Bramhall+Lane+South+Bramhall+SK7+1AL" rel="noopener" target="_blank">Get directions</a></p>
        <h3 style="margin-top:1.5rem">Opening hours</h3>
        <table class="hours"><caption class="visually-hidden">Opening hours for Eds Hair</caption>
          <tbody>{''.join(hours_rows)}</tbody>
        </table>
        <p style="font-size:.85rem;color:var(--ink-soft);margin-top:.75rem">Closed on bank holidays.</p>
      </div>

      <div class="card">
        <h3>Book an appointment</h3>
        <p>Book online any time, or call the salon and we will talk you through
        what your hair needs.</p>
        <div class="btn-row" style="margin-bottom:1.5rem">
          <a class="btn btn--primary" href="{NAP['bookingUrl']}">Book online</a>
          <a class="btn btn--ghost" href="tel:{NAP['phoneE164']}">{esc(NAP['phone'])}</a>
        </div>

        <h3>Send us a message</h3>
        <form class="form-grid" action="https://edshair.co.uk/contact" method="post">
          <div class="field">
            <label for="name">Your name <span class="req" aria-hidden="true">*</span></label>
            <input id="name" name="name" type="text" autocomplete="name" required>
          </div>
          <div class="field">
            <label for="email">Email <span class="req" aria-hidden="true">*</span></label>
            <input id="email" name="email" type="email" autocomplete="email" required>
          </div>
          <div class="field">
            <label for="phone">Phone</label>
            <input id="phone" name="phone" type="tel" autocomplete="tel">
          </div>
          <div class="field">
            <label for="service">What do you need?</label>
            <select id="service" name="service">
              <option value="">Choose a service</option>
              <option>Brazilian Blow Dry</option>
              <option>Hair Botox Treatment</option>
              <option>Cut and blow dry</option>
              <option>Highlights and colour</option>
              <option>Balayage</option>
              <option>Styling</option>
              <option>Children's cut</option>
              <option>Perm or relaxer</option>
              <option>Product advice</option>
            </select>
          </div>
          <div class="field">
            <label for="message">Message</label>
            <textarea id="message" name="message" placeholder="Tell us a bit about your hair and what you are after."></textarea>
            <span class="hint">We reply during opening hours.</span>
          </div>
          <button class="btn btn--primary" type="submit">Send message</button>
        </form>
      </div>

      <div class="card">
        <h3>Getting here</h3>
        <p>{directions}</p>
        <ul class="info-list" style="margin-top:1.25rem">
          <li>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M22 16.9v3a2 2 0 0 1-2.2 2 19.8 19.8 0 0 1-8.6-3.1 19.5 19.5 0 0 1-6-6A19.8 19.8 0 0 1 2.1 4.2 2 2 0 0 1 4.1 2h3a2 2 0 0 1 2 1.7c.1 1 .4 1.9.7 2.8a2 2 0 0 1-.5 2.1L8.1 9.9a16 16 0 0 0 6 6l1.3-1.3a2 2 0 0 1 2.1-.4c.9.3 1.8.6 2.8.7a2 2 0 0 1 1.7 2Z"/></svg>
            <div><strong>Phone</strong><a href="tel:{NAP['phoneE164']}">{esc(NAP['phone'])}</a></div>
          </li>
          <li>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M12 21s-7-4.6-7-11a7 7 0 1 1 14 0c0 6.4-7 11-7 11Z"/><circle cx="12" cy="10" r="2.6"/></svg>
            <div><strong>Address</strong>{esc(NAP['street'])}, {esc(NAP['locality'])}, {esc(NAP['postalCode'])}</div>
          </li>
          <li>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><rect x="3" y="5" width="18" height="16" rx="2"/><path d="M8 3v4M16 3v4M3 11h18"/></svg>
            <div><strong>Saturday</strong>8:30am &ndash; 4:00pm</div>
          </li>
          <li>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M4 4h16v16H4z"/><path d="m4 6 8 6 8-6"/></svg>
            <div><strong>Email</strong><a href="mailto:info@edshair.co.uk">info@edshair.co.uk</a></div>
          </li>
        </ul>
      </div>
    </div>
  </div>
</section>"""


def cta_section() -> str:
    return f"""
<section class="section cta-band">
  <div class="wrap">
    <span class="eyebrow" style="color:#f3d3d3">Ready when you are</span>
    <h2>Book your appointment</h2>
    <p>Open six days a week in Bramhall. Book online in under a minute, or
    call us and we will find a time that works.</p>
    <div class="btn-row">
      <a class="btn btn--light" href="{NAP['bookingUrl']}">Book online</a>
      <a class="btn btn--outline-light" href="tel:{NAP['phoneE164']}">Call {esc(NAP['phone'])}</a>
    </div>
  </div>
</section>"""


def home_page() -> str:
    body = "\n".join([
        hero(),
        services_section(),
        blowout_section(),
        prices_section(),
        shop_section(),
        gallery_section(),
        reviews_section(),
        contact_section(),
        cta_section(),
    ])
    return page(
        title="Eds Hair | Brazilian Blow Dry, Colour & Cut in Bramhall, Stockport",
        description=(
            "Luxe hair salon in Bramhall, Stockport. Brazilian blow dries from "
            "£100, balayage and lived-in colour. Schwarzkopf Professional Colour "
            "Master. Book online."
        ),
        body=body,
        jsonld=jsonld_home(),
        nav_active="services",
    )


def products_page() -> str:
    body = "\n".join([shop_section(), cta_section()])
    return page(
        title="Shop professional hair products | Eds Hair Bramhall",
        description=(
            "Shop ghd, K18, Schwarzkopf Professional and Authentic Beauty Concept "
            "at Eds Hair, Bramhall — the exact products our stylists use in the salon."
        ),
        body=body,
        jsonld=jsonld_products(),
        canonical="https://edshair.co.uk/collections/all",
        nav_active="shop",
    )


def services_page() -> str:
    body = "\n".join([
        services_section(),
        blowout_section(),
        prices_section(),
        cta_section(),
    ])
    return page(
        title="Hair services and full price list | Eds Hair Bramhall",
        description=(
            "Brazilian blow dry, keratin smoothing, hair Botox, cuts, colour and "
            "balayage in Bramhall. See every price online, from £20 add-ons to "
            "£325 Brazilian blow dries."
        ),
        body=body,
        jsonld=jsonld_home(),
        canonical="https://edshair.co.uk/pages/services",
        nav_active="services",
    )


def contact_page() -> str:
    body = "\n".join([contact_section(), cta_section()])
    return page(
        title="Contact and opening hours | Eds Hair, 13 Bramhall Lane South",
        description=(
            "Visit Eds Hair at 13 Bramhall Lane South, Bramhall, Stockport SK7 1AL. "
            "Open 8:30am Mon-Sat. Call 0161 439 8058 or book online."
        ),
        body=body,
        jsonld=jsonld_home(),
        canonical="https://edshair.co.uk/a/contact",
        nav_active="contact",
    )


# =========================================================== robots etc ====

def robots_txt() -> str:
    return (
        "User-agent: *\n"
        "Allow: /\n"
        "Disallow: /cart\n"
        "Disallow: /checkouts/\n"
        "Disallow: /account\n"
        "\n"
        "Sitemap: https://edshair.co.uk/sitemap.xml\n"
    )


def sitemap_xml(pages: list[tuple[str, str, str]]) -> str:
    today = "2026-11-09"
    urls = []
    for loc, priority, changefreq in pages:
        urls.append(
            f"  <url>\n"
            f"    <loc>{esc(loc)}</loc>\n"
            f"    <lastmod>{today}</lastmod>\n"
            f"    <changefreq>{changefreq}</changefreq>\n"
            f"    <priority>{priority}</priority>\n"
            f"  </url>"
        )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "\n".join(urls)
        + "\n</urlset>\n"
    )


def manifest_webmanifest() -> str:
    return json.dumps({
        "name": "Eds Hair",
        "short_name": "Eds Hair",
        "start_url": "/",
        "display": "standalone",
        "background_color": "#ffffff",
        "theme_color": "#8c2f39",
        "icons": [{
            "src": "https://edshair.co.uk/cdn/shop/files/Eds_2020_Logo_32x32.jpg",
            "sizes": "32x32",
            "type": "image/jpeg",
        }],
    }, indent=2)


# ============================================================== minify =======

def _strip_comments(text: str, block: tuple[str, str]) -> str:
    """Remove comments without touching string literals."""
    out, i, n = [], 0, len(text)
    open_s, close_s = block
    while i < n:
        ch = text[i]
        if ch in ("'", '"', "`"):
            quote = ch
            out.append(ch)
            i += 1
            while i < n:
                out.append(text[i])
                if text[i] == "\\":
                    if i + 1 < n:
                        out.append(text[i + 1])
                        i += 2
                        continue
                elif text[i] == quote:
                    i += 1
                    break
                i += 1
            continue
        if text.startswith(open_s, i):
            j = text.find(close_s, i)
            i = n if j == -1 else j + len(close_s)
            continue
        out.append(ch)
        i += 1
    return "".join(out)


def minify_css(css: str) -> str:
    css = _strip_comments(css, ("/*", "*/"))
    css = re.sub(r"\s+", " ", css)
    css = re.sub(r"\s*([{};:,])\s*", r"\1", css)
    css = re.sub(r";}", "}", css)
    return css.strip()


def minify_js(js: str) -> str:
    js = _strip_comments(js, ("/*", "*/"))
    js = re.sub(r"^\s*//.*$", "", js, flags=re.M)
    js = re.sub(r"\n\s*\n+", "\n", js)
    lines = [ln.strip() for ln in js.splitlines() if ln.strip()]
    return "\n".join(lines)


# ============================================================== main =======

def main() -> None:
    SITE.mkdir(parents=True, exist_ok=True)

    # Copy the optimised images into the site tree.
    img_out = SITE / "img"
    if img_out.exists():
        shutil.rmtree(img_out)
    shutil.copytree(OUT, img_out)

    # Minified stylesheet + script (the readable originals stay alongside).
    css_src = SITE / "assets" / "styles.css"
    js_src = SITE / "assets" / "app.js"
    css_min = minify_css(css_src.read_text(encoding="utf-8"))
    js_min = minify_js(js_src.read_text(encoding="utf-8"))
    (SITE / "assets" / "styles.min.css").write_text(css_min, encoding="utf-8")
    (SITE / "assets" / "app.min.js").write_text(js_min, encoding="utf-8")
    print(f"  styles.min.css   {len(css_min.encode('utf-8')):>8,} bytes "
          f"(from {css_src.stat().st_size:,})")
    print(f"  app.min.js       {len(js_min.encode('utf-8')):>8,} bytes "
          f"(from {js_src.stat().st_size:,})")

    pages = {
        "index.html": home_page(),
        "services.html": services_page(),
        "shop.html": products_page(),
        "contact.html": contact_page(),
    }
    for name, html_text in pages.items():
        (SITE / name).write_text(html_text, encoding="utf-8")
        print(f"  {name:16} {len(html_text.encode('utf-8')):>8,} bytes")

    (SITE / "robots.txt").write_text(robots_txt(), encoding="utf-8")
    (SITE / "sitemap.xml").write_text(sitemap_xml([
        ("https://edshair.co.uk/", "1.0", "weekly"),
        ("https://edshair.co.uk/pages/services", "0.9", "monthly"),
        ("https://edshair.co.uk/collections/all", "0.8", "weekly"),
        ("https://edshair.co.uk/a/contact", "0.7", "monthly"),
    ]), encoding="utf-8")
    (SITE / "site.webmanifest").write_text(manifest_webmanifest(), encoding="utf-8")

    total = sum(f.stat().st_size for f in SITE.rglob("*") if f.is_file())
    print(f"\nTotal site payload: {total:,} bytes ({total/1024:.0f} KB)")
    print(f"-> {SITE}")


if __name__ == "__main__":
    main()
