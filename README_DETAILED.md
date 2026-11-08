# Data Scalper - Complete Technical Documentation

## Overview

Data Scalper is a lead generation tool that finds local businesses without websites (or with only social media presence) and helps you contact them. It pulls business data from multiple public and API sources, classifies businesses by their website presence, and provides outreach tools.

---

## DATA SOURCES

This project pulls business data from **four different sources**. Each has different characteristics, coverage, and legal/compliance considerations.

### 1. Overture Maps (Default - Free, No API Key Required)

**Where the data comes from:**
- Overture Maps is an open data initiative by Meta, Microsoft, Amazon, and other tech companies
- Data is read directly from Overture's public S3 bucket: `s3://overturemaps-us-west-2/release/{release}/theme=places/type=place/*`
- Uses DuckDB to query Parquet files, downloading only rows within the search area
- No API key required - completely free

**What data it provides:**
- Business name, address, phone numbers, email addresses
- Websites and social media links (primarily Facebook)
- Operating status (open/closed)
- Business categories (taxonomy)
- Confidence scores for data reliability

**How it works:**
1. User searches by keyword, category, and location (city + radius)
2. The app geocodes the location using OpenStreetMap's Nominatim (free, no key)
3. Uses DuckDB to query Overture's S3 data for places within the geographic bounding box
4. Filters by category taxonomy and keyword matches
5. Excludes chains/franchises (via Wikidata brand tags and name repetition)
6. Returns up to 1000 results sorted by: (1) no website first, (2) confidence score, (3) distance

**Data Accuracy:**
- ⚠️ **Data can be outdated** - phone numbers, emails, and Facebook pages come from public listings that may no longer be current
- The app explicitly warns users to verify data before contacting
- Data is crowdsourced from OpenStreetMap and other public sources
- Confidence scores help identify more reliable entries

**Legal Status:**
- ✅ **LEGAL** - Overture Maps data is licensed under CDLA-Permissive (Community Data License Agreement)
- This is an open license that allows commercial use
- Crediting "Overture Maps Foundation" is good practice but not legally required
- The data is voluntarily contributed by users and companies to open mapping projects

**Coverage:**
- Worldwide coverage
- Best for: restaurants, cafes, retail, service businesses
- May have limited data for trades (plumbers, electricians) in some areas

---

### 2. Geoapify API (Free Tier Available)

**Where the data comes from:**
- Geoapify is a commercial geospatial API provider
- Data source: OpenStreetMap (OSM) and other open data providers
- API endpoint: `https://api.geoapify.com/v2/places`
- Requires API key (free tier: 3000 requests/day)

**What data it provides:**
- Business name, address, phone numbers
- Email addresses (when available)
- Website URLs
- Business categories
- Geographic coordinates

**How it works:**
1. Geocodes the search location using Geoapify's geocoding API
2. Searches the Places API with:
   - Category filters (predefined business types)
   - Geographic radius filter
   - Keyword text filters (for trades without categories)
3. Paginates through results (up to 5 pages × 100 places)
4. Returns normalized lead data

**Data Accuracy:**
- Data comes from OpenStreetMap - user-contributed and can be incomplete
- Phone/email data is often missing for many businesses
- The app warns when no keyword matches are found in the first 500 businesses

**Legal Status:**
- ✅ **LEGAL** - Geoapify aggregates data from OpenStreetMap (ODbL license)
- ODbL (Open Database License) allows commercial use with attribution
- Geoapify's terms of service must be followed
- Free tier available for low-volume use
- Paid tiers available for higher volume

**Coverage:**
- Worldwide coverage
- Better for businesses with physical locations (retail, restaurants)
- Limited for trades without category mappings

---

### 3. Google Places API (New)

**Where the data comes from:**
- Google's official Places API (New version)
- API endpoint: `https://places.googleapis.com/v1/places:searchText`
- Requires Google Cloud API key
- Free quota available, then paid (requires quota cap setup)

**What data it provides:**
- Business name, address, phone numbers
- Website URLs
- User ratings and review counts
- Business status (operational/closed)
- Business types/categories

**How it works:**
1. Geocodes location using Google Geocoding API
2. Uses Text Search endpoint with:
   - Text query (keyword + location)
   - Location bias (circular radius around coordinates)
   - Category type filters
   - Country/region codes
3. Paginates through results (up to 3 pages × 20 places = 60 max)
4. Returns normalized lead data

**Data Accuracy:**
- ⭐ **HIGH** - Google's data is generally the most accurate and up-to-date
- Regularly updated by Google's verification processes
- Phone numbers and websites are usually current
- User ratings provide additional quality signals

**Legal Status:**
- ✅ **LEGAL** - Official Google API with clear terms of service
- Must comply with Google Maps Platform Terms of Service
- Requires billing setup (even for free quota)
- Must display attribution when displaying Google data
- Rate limits and quotas enforced

**Coverage:**
- Worldwide coverage, but varies by region
- Best for established businesses on Google Maps
- Excellent coverage in most countries
- May miss very new or unverified businesses

**Cost:**
- Free quota: $200/month credit
- After quota: $0.032 per 1,000 requests (Text Search)
- Geocoding: $5 per 1,000 requests
- ⚠️ **WARNING**: Must set quota caps to avoid unexpected charges

---

### 4. Companies House API (UK Only)

**Where the data comes from:**
- Official UK government registry of companies
- API endpoint: `https://api.company-information.service.gov.uk`
- Free API key required (600 requests / 5 minutes)
- Only covers UK-registered companies

**What data it provides:**
- Company name, registered address
- Incorporation date
- SIC codes (industry classification)
- Company status (active/dissolved)
- Director names (via separate API call)
- ⚠️ **NO phone numbers or websites** - these are not in the registry

**How it works:**
1. Searches the Advanced Search endpoint with:
   - SIC code filters (industry types)
   - Location filters
   - Company name keyword filters
   - Incorporation date filters (for new companies)
2. Fetches director information via the Officers endpoint
3. Provides Google Search links to find phone/websites externally

**Data Accuracy:**
- ⭐ **HIGH** - Official government data, highly accurate
- Incorporation dates and addresses are legally required
- Director information is official
- ⚠️ Missing phone/website - user must search Google manually

**Legal Status:**
- ✅ **LEGAL** - Official UK government open data
- Crown Copyright / Open Government License
- Free to use for commercial purposes
- Must follow Companies House API terms
- Rate limited to 600 requests per 5 minutes

**Coverage:**
- UK only (England, Wales, Scotland, Northern Ireland)
- Limited to registered companies (Ltd, LLP, PLC, etc.)
- Does NOT include sole traders or partnerships
- Best for finding newly incorporated UK companies

---

## DATA CLASSIFICATION

### Website Classification System

The app uses `website_classifier.py` to categorize business websites into three types:

#### 1. NO WEBSITE
- Empty or null website field
- Business truly has no web presence

#### 2. SOCIAL ONLY
- Website is a social media profile:
  - facebook.com, fb.com, instagram.com, linkedin.com, twitter.com/x.com
  - tiktok.com, youtube.com, pinterest.com
- Free site builder subdomain:
  - wixsite.com, business.site, sites.google.com
  - weebly.com, blogspot.com, wordpress.com
  - carrd.co, square.site, godaddysites.com
- Directory or booking page:
  - g.page, maps.app.goo.gl, yell.com
  - checkatrade.com, trustpilot.com, yelp.com
  - tripadvisor.com, bark.com, mybuilder.com
  - fresha.com, booksy.com, opentable.com
  - ubereats.com, just-eat.co.uk, deliveroo.co.uk

#### 3. HAS WEBSITE
- Custom domain (e.g., `example.com`)
- Subdomain of own domain (e.g., `shop.example.com`)
- Indicates a real business-owned website

**Important**: Both "NO WEBSITE" and "SOCIAL ONLY" are considered "needs website" leads for outreach purposes.

---

## DATA LEGALITY & COMPLIANCE

### Is the data legal to use?

**YES** - All data sources are legal:

1. **Overture Maps**: Open data (CDLA-Permissive license) - commercial use allowed
2. **Geoapify**: OpenStreetMap data (ODbL license) - commercial use allowed
3. **Google Places**: Official API with clear terms - commercial use allowed
4. **Companies House**: UK government open data - commercial use allowed

### Is the data from accurate places?

**VARIES BY SOURCE**:

- **Google Places**: Most accurate and up-to-date
- **Companies House**: Highly accurate (official government data)
- **Geoapify**: Moderate accuracy (OpenStreetMap, user-contributed)
- **Overture Maps**: Moderate accuracy (aggregated from multiple sources)

### ⚠️ IMPORTANT LIMITATIONS

1. **Data can be outdated**: Phone numbers, emails, and social links may no longer be current
2. **Always verify**: The app provides Google Search, Map, and direct links to verify before contacting
3. **Missing data**: Not all sources have phone/email for every business
4. **Crowdsourced errors**: OpenStreetMap and Overture data can have user errors
5. **No scraping**: The app uses official APIs and open data - it does not scrape websites

---

## OUTREACH LEGAL CONSIDERATIONS

### Cold Contact Rules by Country

The app provides this warning in the README:

> "Cold-contact rules differ by country (UK/EU GDPR + PECR, Canada CASL, Australia Spam Act, US CAN-SPAM). Sole traders are the riskiest to email — call or WhatsApp first. Always include an opt-out line and stop when someone asks."

**Key Points:**
- **UK/EU**: GDPR + PECR regulate cold emails - need consent or legitimate interest
- **Canada**: CASL requires express consent for commercial emails
- **Australia**: Spam Act 2003 with strict consent requirements
- **US**: CAN-SPAM allows cold emails but requires opt-out mechanism

**Best Practices:**
1. Verify the business is real before contacting
2. Include clear opt-out language in messages
3. Stop immediately when asked
4. Consider calling or WhatsApp first for sole traders
5. Follow local laws for your jurisdiction

---

## HOW THE APP WORKS - END-TO-END

### Search Flow

1. **User Input**:
   - Selects data source (Overture, Geoapify, Google, Companies House)
   - Enters keyword (e.g., "plumbers") or selects category
   - Chooses target country and city/cities
   - Sets search radius and max results

2. **Geocoding**:
   - Converts city name to coordinates (lat/lon)
   - Uses Nominatim (Overture) or provider-specific geocoding

3. **API/Data Query**:
   - Calls the selected provider's search function
   - Applies filters (category, keyword, radius, max results)
   - Paginates through results if needed

4. **Data Enrichment**:
   - Normalizes phone numbers (international format)
   - Classifies websites (NO WEBSITE / SOCIAL ONLY / HAS WEBSITE)
   - Determines phone type (mobile vs landline for WhatsApp)
   - Adds Google Search, Facebook Search, LinkedIn Search links
   - Scores leads based on multiple factors

5. **Lead Scoring**:
   - Higher score = better lead to contact
   - Factors: phone availability, email availability, website status, etc.

6. **Display**:
   - Results shown in table sorted by score
   - User can filter by "No website" or "Has website (redesign)"
   - Each lead has a detailed card with contact options

### Contact Flow

1. **Lead Selection**: User clicks a lead from the table
2. **Verification**: User opens Map/Google/Facebook links to verify business
3. **Contact**: User chooses WhatsApp/Call/Email buttons
4. **Messaging**: App generates personalized message templates
5. **Status Update**: User marks lead as "Called", "Messaged", "Won", etc.
6. **Follow-up**: App tracks follow-up dates and reminders

---

## DATA STORAGE

### Files Created

| File | Purpose |
|------|---------|
| `leads.db` | SQLite database with all found leads |
| `cache.json` | User edits (Contacted status, Manual Email) |
| `clients.json` | Won projects (client details, payments) |
| `outreach_settings.json` | User's details and message templates |

**Backup**: The app provides a "Prepare backup (.zip)" feature in the sidebar to download all four files.

---

## API KEY SETUP

### Required Keys (Optional but Recommended)

1. **GEOAPIFY_API_KEY** (Free tier available)
   - Sign up: https://www.geoapify.com/
   - Free: 3000 requests/day

2. **GOOGLE_PLACES_API_KEY** (Free quota, then paid)
   - Sign up: https://console.cloud.google.com/
   - Enable: Places API, Geocoding API
   - ⚠️ Set quota caps to avoid charges

3. **COMPANIES_HOUSE_API_KEY** (Free, UK only)
   - Sign up: https://developer.company-information.service.gov.uk/get-started
   - Free: 600 requests / 5 minutes

4. **AI Keys** (Optional, for website generation)
   - GEMINI_API_KEY: https://aistudio.google.com/apikey
   - GROQ_API_KEY: https://console.groq.com/keys
   - OPENROUTER_API_KEY: https://openrouter.ai/keys

### No Key Required

- **Overture Maps**: Works out of the box, completely free

---

## RECOMMENDATIONS

### For Best Results

1. **Start with Overture Maps** - Free, worldwide, includes email/Facebook
2. **Use Google Places** for highest accuracy when budget allows
3. **Use Companies House** for UK newly incorporated companies
4. **Always verify** data before contacting using the provided links
5. **Follow local laws** for cold outreach in your country

### Data Source Selection Guide

| Need | Best Source |
|------|-------------|
| Free, worldwide, email/Facebook data | Overture Maps |
| Highest accuracy, reviews | Google Places |
| UK new companies only | Companies House |
| European businesses | Geoapify |
| Trades (plumbers, electricians) | Google Places or Overture |

---

## SUMMARY

**Is the data legal?** ✅ YES - All sources use legal APIs or open data licenses

**Is the data accurate?** ⭐⭐⭐⭐☆ Varies - Google is most accurate, others moderate

**Is it pulling from the right places?** ✅ YES - Uses official APIs and open data sources

**Is it scraping?** ❌ NO - Uses official APIs and open data buckets

**Should I verify before contacting?** ✅ YES - Always verify using the provided links

**Is it suitable for commercial use?** ✅ YES - All licenses allow commercial use

---

## Technical Implementation

### Key Files

- `app.py` - Main Streamlit application
- `overture_api.py` - Overture Maps data provider
- `geoapify_api.py` - Geoapify API wrapper
- `places_api.py` - Google Places API wrapper
- `companies_house_api.py` - UK Companies House API wrapper
- `website_classifier.py` - Website URL classification
- `lead_scorer.py` - Lead scoring algorithm
- `outreach.py` - Message generation and contact management

### Dependencies

- streamlit - Web UI framework
- requests - HTTP client for API calls
- pandas - Data manipulation
- duckdb - Query Overture Parquet files
- phonenumbers - Phone number parsing
- python-dotenv - Environment variable management

---

## Conclusion

Data Scalper pulls business data from legitimate, legal sources using official APIs and open data licenses. The data is generally accurate but can be outdated, so verification is always recommended. The tool is designed for legitimate lead generation for web design services, with built-in features to verify businesses before contact.
