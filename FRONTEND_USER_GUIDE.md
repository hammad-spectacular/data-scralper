# Data Scalper - Complete Frontend User Guide

## TABLE OF CONTENTS
1. [Overview](#overview)
2. [Search Card - Finding Businesses](#search-card---finding-businesses)
3. [Results Tabs](#results-tabs)
4. [Lead Contact Workflow](#lead-contact-workflow)
5. [Sidebar Configuration](#sidebar-configuration)
6. [Complete Workflow Example](#complete-workflow-example)

---

## OVERVIEW

The Data Scalper frontend is designed to help you:
1. **Find** businesses that need websites (or have bad websites)
2. **Contact** them with personalized messages
3. **Track** your outreach and follow-ups
4. **Generate** website mockups to show prospects

The interface is built with Streamlit and has 5 main sections:
- **Search Card** (top) - Find businesses
- **KPI Cards** - Show statistics
- **5 Tabs** - Manage leads, follow-ups, clients, downloads
- **Sidebar** - Configuration and settings

---

## SEARCH CARD - FINDING BUSINESSES

### Step 1: Choose Data Source

At the top of the page, you'll see a radio button to select your data source:

#### **Option 1: Overture Maps (Recommended - Free)**
- ✅ **No API key required**
- ✅ Worldwide coverage
- ✅ Includes phone, email, and Facebook page
- ⏱️ Search takes 30-50 seconds
- 📊 Returns up to 1000 results

**Best for:** Most use cases, especially when starting out

#### **Option 2: Geoapify (Free Tier)**
- 🔑 Requires API key (3000 free requests/day)
- 🌍 Worldwide coverage
- 📊 Returns up to 5000 results
- ⚠️ Often lacks website data (verify manually)

**Best for:** When you have a Geoapify key and need more results

#### **Option 3: Google Places (Paid after quota)**
- 🔑 Requires Google Cloud API key
- ⭐ Most accurate data
- ⭐ Includes ratings and reviews
- 💰 Free quota ($200/month), then paid
- 📊 Returns up to 60 results

**Best for:** When budget allows and you need highest accuracy

#### **Option 4: Companies House (UK Only)**
- 🔑 Requires free API key
- 🇬🇧 UK only
- 📊 Returns up to 500 results
- ⚠️ No phone numbers or websites (must search Google)

**Best for:** Finding newly incorporated UK companies

---

### Step 2: Enter Search Criteria

#### For Overture, Geoapify, Google Places:

**Column 1:**
- **Keyword** (optional): e.g., "plumbers", "hair salon", "accountants"
- **Category** (optional): Select from dropdown
  - Overture: Can select multiple categories
  - Geoapify/Google: Single category
  - Examples: "Hair & beauty", "Restaurants", "Plumbers", etc.

**Column 2:**
- **Target Country**: Select from dropdown (default: United Kingdom)
- **City or Postcode**: e.g., "Manchester", "SW1A 1AA"
  - Can search multiple cities with semicolon: "Leeds; Bradford; Sheffield"
  - Max results applies to EACH city

**Column 3:**
- **🔍 Search Button**: Click to run the search

#### For Companies House (UK only):

**Column 1:**
- **Business Type**: Select industry (e.g., "Hair & beauty", "Plumbing")
- **Extra SIC Codes**: Optional specific codes (e.g., "96020, 43220")
- **Company Name Contains**: Optional keyword (e.g., "barber")

**Column 2:**
- **Town or Postcode**: e.g., "Manchester", "SW1A 1AA"
- **Registered in last… months**: Slider (0-60, default 12)
  - Newer companies = better leads (likely no website yet)
- **Look up director names**: Checkbox
  - Adds ~0.5s per company
  - Gives you a first name for personalized greetings

**Column 3:**
- **🔍 Search Button**: Click to run the search

---

### Step 3: Configure Search Options (Advanced)

Click **"⚙️ Search options — filters, radius, how many results"** to expand:

#### Location Settings:
- **Location Type**:
  - "City / Postcode name" (default)
  - "Lat / Lng + Radius" (for precise coordinates)
- **Radius (km)**: Slider from 1-50 km (default 10 km)
  - Larger radius = more results, but less relevant

#### Result Limits:
- **Max results to fetch**:
  - Google: Max 60
  - Companies House: Max 500
  - Overture: Max 1000
  - Geoapify: Max 5000
  - Default varies by provider

#### Filters:
- **Reuse results of identical searches (1 h)**: ✅ Checked by default
  - Saves API quota
  - Untick to force fresh search
- **Hide permanently closed businesses**: ✅ Checked by default
  - Don't show closed/out-of-business
- **Hide leads I already contacted**: ✅ Checked by default
  - Only show leads with "Not contacted" status
- **Only show leads never found before**: ☐ Unchecked by default
  - Useful for finding NEW businesses in area
- **Skip big chains / franchises**: ✅ Checked by default
  - Excludes McDonald's, Costa, etc.
  - Also excludes names appearing 3+ times

---

### Step 4: Run the Search

Click the **🔍 Search** button.

**What happens:**
1. App queries the selected data source
2. Geocodes the city to coordinates
3. Fetches businesses within radius
4. Classifies websites (NO WEBSITE / SOCIAL ONLY / HAS WEBSITE)
5. Scores leads (0-100)
6. Filters based on your options
7. Displays results in the tabs below

**Search time:**
- Overture: 30-50 seconds (first time), cached for 1 hour
- Geoapify: 5-15 seconds
- Google Places: 5-10 seconds
- Companies House: 10-30 seconds

---

## RESULTS TABS

After searching, you'll see **5 tabs** at the top:

### Tab 1: 🎯 Leads to Contact (Main Workflow)

**This is where you'll spend most of your time.**

#### Subsection: Choose Target Type

Two radio buttons:

**Option A: 🚫 No website** (default)
- Shows businesses with NO website or only social media
- These are your best leads
- Pitch: "You don't have a website yet"

**Option B: 🔄 Has a website — redesign pitch**
- Shows businesses that already have a website
- Pitch: "Your website could be better"
- Requires you to evaluate their current site first

#### Subsection: Lead Selection Table

**Table columns:**
- **Name**: Business name
- **Town**: City/town
- **Score**: Lead score (0-100, higher = better)
- **Website**: "NO WEBSITE", "SOCIAL ONLY", or "HAS WEBSITE"
- **Phone**: Phone number
- **Type**: "Mobile" or "Landline"
- **Local time**: Current time at business location
- **Status**: Contact status (Not contacted, Called, etc.)

**How to use:**
1. **Click a row** to select that lead
2. The lead details card appears below
3. Use **Prev/Next** buttons to navigate
4. Look for:
   - ✅ in "Local time" = good time to call
   - Higher Score = better lead
   - Mobile phone = can use WhatsApp

#### Subsection: Lead Contact Card

When you select a lead, a detailed card appears:

**Top Section:**
- Business name and address
- Badges showing:
  - Website status (red for NO WEBSITE, amber for SOCIAL ONLY)
  - Lead score (green if ≥70)
  - Phone type (Mobile/Landline)
  - Local time and call window (green if good time)

**Navigation:**
- **◀ Prev**: Go to previous lead
- **Next ▶**: Go to next lead
- Shows "Lead X of Y"

**Action Buttons:**
- **🌐 Their website**: Opens their website (redesign mode only)
- **💬 WhatsApp**: Opens WhatsApp with pre-filled message
- **📞 Call**: Opens phone dialer
- **✉️ Email**: Opens email client with pre-filled message
- **📍 Map**: Opens Google Maps
- **🔍 Google**: Opens Google search for the business
- **📘 Facebook**: Opens Facebook search

**Best Practice:**
1. **ALWAYS** open Map and Google links first
2. Verify the business is real
3. Confirm they really have no website
4. THEN use WhatsApp/Call/Email

**Status Update:**
- **Status dropdown**: Update after contacting
  - Options: Not contacted, Called, Messaged, Followed up, Replied, Won, Not interested
- **Email field**: Add email if you find one (email button will appear)

**Message Tabs:**

**Tab A: 💬 Messages**
- Shows pre-generated email subject and body
- Shows pre-generated WhatsApp message
- Copy and send these messages
- Edit templates in sidebar

**Tab B: 🎨 Sample Website**
- Two options for generating mockups:

**Option 1: ⚡ Instant Template (No AI key needed)**
- Automatically generated HTML mockup
- Uses lead's real name, address, phone
- Services and hours are marked as "example"
- **📥 Download this mockup (.html)**: Download single mockup
- **📦 Prepare ZIP of all mockups**: Download all leads' mockups
- **👁️ Preview template**: Preview in browser

**Option 2: 🤖 AI-Designed Page (Requires AI API key)**
- Uses Groq, Gemini, or OpenRouter
- Generates custom website with AI
- Select AI provider (e.g., "Groq (free, no card)")
- Enter API key (or add to .env file)
- Select style (Modern & clean, Bold & dark, etc.)
- Add extra wishes (optional)
- Click **✨ Generate website with AI**
- Takes 10-60 seconds
- **📥 Download AI website (.html)**: Download the generated page
- Warnings shown if AI invented facts

**Tab C: 🧠 Prompts for ChatGPT / Claude**
- Professional prompt to paste into ChatGPT/Claude
- Includes all lead's real facts
- More polished than built-in AI generator
- Copy the prompt, paste into ChatGPT/Claude
- Get a professional website back

**Tab D: 📇 Details**
- All known information about the lead
- Name, address, phone, email, website
- Business status, types, source
- Google/Facebook/LinkedIn search links

---

### Tab 2: 📊 All Results

Shows **ALL** businesses found in the search (not just those needing websites).

**Table columns:**
- Name, Address, Phone, Phone Type
- Local Time, Call Window
- Website Status, Social Link
- Rating, Reviews, Lead Score
- Best Channel (WhatsApp/Call/Email)
- Google Maps link
- Business Status
- Source (which data provider)
- First Seen, Last Seen
- Manual Email (editable)
- Contacted (editable dropdown)

**Metrics at bottom:**
- 🚫 No Website: Count
- 📱 Social Only: Count
- ✅ Has Website: Count

**Use this tab to:**
- See the full picture of the market
- Edit contact status in bulk
- Add manual emails
- Export all results

---

### Tab 3: 📅 Follow-ups & Stats

Shows leads waiting for a reply.

**Settings:**
- **Follow-up after X days**: Default 4 days
- Shows leads contacted X+ days ago with no reply

**Table columns:**
- Name, Town, Contacted status
- Days Since Contacted
- Manual Email
- Contacted On date

**Stats section:**
- **Contacts per day (last 14 days)**: Bar chart
- **Reply rate**: (Replied + Won) / contacted
- **Status breakdown**: Count per status

**Use this tab to:**
- Track who needs follow-up
- Monitor your response rate
- See your daily activity

---

### Tab 4: 💼 Clients

Shows businesses you **won** (converted to clients).

**Table columns:**
- Name, Town
- Package (e.g., "Basic website")
- Price (numeric)
- Currency (USD, GBP, EUR, etc.)
- Paid (numeric)
- Outstanding (Price - Paid)
- Deadline
- Notes

**Editable:**
- All fields except Name, Town
- Click cells to edit

**Use this tab to:**
- Track won projects
- Monitor payments
- Manage deadlines
- Track revenue

---

### Tab 5: ⬇️ Downloads

Export options:

**CSV Downloads:**
- **📥 All results (.csv)**: All businesses from search
- **📥 Leads to contact (.csv)**: Only leads needing websites
- **📥 Follow-ups (.csv)**: Leads needing follow-up
- **📥 Clients (.csv)**: Won projects

**Backup:**
- **💾 Prepare backup (.zip)**: Downloads all data files
  - leads.db (all leads ever found)
  - cache.json (your edits)
  - clients.json (won projects)
  - outreach_settings.json (your templates)

**Use this tab to:**
- Export data for Excel/Google Sheets
- Backup your work
- Move data between computers

---

## SIDEBAR CONFIGURATION

The left sidebar has several sections:

### Section 1: 💾 Saved Leads

**Open saved leads**:
- Click to load all previously saved leads
- Shows all leads from leads.db
- Replaces current search results

**Backup**:
- **💾 Prepare backup (.zip)**: Download all data files
- **🗑️ Delete all leads**: Clear leads.db (⚠️ destructive)

### Section 2: 📝 Your Details & Message Templates

**Your Details:**
- **Your name**: Your name (used in messages)
- **Your business**: Your business name
- **Your phone**: Your phone number
- **Portfolio link**: Link to your portfolio
- **Default follow-up after X days**: Default 4

**Message Templates:**
- **Email subject**: e.g., "A website for {business_name}?"
- **Email body**: Full email template
- **WhatsApp message**: Short conversational message
- **Follow-up message**: Follow-up template
- **Redesign subject**: For businesses with websites
- **Redesign email body**: Redesign pitch email
- **Redesign WhatsApp**: Redesign pitch WhatsApp

**Placeholders:**
- `{greeting}`: "Hi", "Hello", etc.
- `{business_name}`: Lead's business name
- `{business_type}`: e.g., "plumbers", "hair salon"
- `{town}`: Lead's city
- `{first_name}`: Director's first name (if available)
- `{sender_name}`: Your name
- `{from_business}`: " from [your business]"
- `{signature}`: Your signature
- `{days}`: Default turnaround time
- `{website}`: Their current website (redesign mode)
- `{observation}`: What you noticed about their site

**Multiple options:**
- Use `{option1|option2|option3}` to randomly pick one
- Example: `{I'm|My name is}` = picks one per lead

**Reset button:**
- Revert to default templates

### Section 3: 🇬🇧 Companies House CSV (UK Only)

**Upload CSV**:
- Upload Companies House bulk download
- Formats: Officers CSV, Basic company data
- **🚀 Process File**: Convert to leads
- Shows director names if Officers CSV loaded

### Section 4: 🔑 API Keys Status

Shows which API keys are configured:
- ✅ Geoapify
- ✅ Google Places
- ✅ Companies House
- ✅ Gemini (AI)
- ✅ Groq (AI)
- ✅ OpenRouter (AI)
- ➖ Overture Maps (no key needed)

### Section 5: ℹ️ Lead Score Formula

Shows how leads are scored:
- Rating: 20 pts max
- Reviews (log-scaled): 30 pts max
- No website (social only = ⅔): 30 pts max
- Has phone number: 20 pts max
- Has email (when no ratings): 10 pts max
- Total max = 100 pts

---

## COMPLETE WORKFLOW EXAMPLE

### Scenario: Finding web design clients in Manchester

#### Step 1: Initial Setup
1. Open sidebar → "Your Details & Message Templates"
2. Fill in:
   - Your name: "John Smith"
   - Your business: "Smith Web Design"
   - Your phone: "+44 7123 456789"
   - Portfolio link: "https://smithwebdesign.com"
3. Review message templates (customize if desired)
4. Close sidebar

#### Step 2: Search for Leads
1. In Search Card:
   - Data source: "Overture Maps (free · worldwide · phone + email)"
   - Keyword: "plumbers"
   - Category: "Plumbers"
   - Target country: "United Kingdom"
   - City: "Manchester"
2. Expand "Search options":
   - Radius: 15 km
   - Max results: 200
   - Hide permanently closed: ✅
   - Hide leads I already contacted: ✅
   - Skip big chains: ✅
3. Click **🔍 Search**
4. Wait 30-50 seconds

#### Step 3: Review Results
1. Look at KPI cards at top:
   - In view: 150 businesses
   - Need website: 85
   - Saved: 0 (first search)
   - Follow-ups: 0
   - Won: 0
2. Click **"🎯 Leads to contact"** tab
3. Verify: "Who do you want to message?" = "🚫 No website"
4. See table of 85 leads sorted by score

#### Step 4: Contact First Lead
1. Click the first row (highest score)
2. Lead card appears:
   - Name: "ABC Plumbing Services"
   - Address: "123 High St, Manchester"
   - Badges: "NO WEBSITE" (red), "Score 78" (green), "Mobile", "10:30 AM ✅"
3. **VERIFY FIRST**:
   - Click **📍 Map** → Confirm location is real
   - Click **🔍 Google** → Search for business
   - Confirm they exist and have no website
4. **Contact them**:
   - Option A: Click **💬 WhatsApp** → Send message
   - Option B: Click **✉️ Email** → Send email
   - Option C: Click **📞 Call** → Call them
5. **Update status**:
   - Change "Status" dropdown to "Messaged" or "Called"
6. **Generate mockup** (optional):
   - Click **"🎨 Sample website"** tab
   - Click **"📥 Download this mockup (.html)"**
   - Send to lead if they express interest

#### Step 5: Move to Next Lead
1. Click **Next ▶** button
2. Repeat verification and contact process
3. Continue for 10-15 leads per day (don't overdo it)

#### Step 6: Follow Up
1. After 4 days, click **"📅 Follow-ups & stats"** tab
2. See leads waiting for reply
3. Send follow-up messages using the follow-up template
4. Update status to "Followed up"

#### Step 7: Handle Responses
1. If lead replies positively:
   - Generate AI website or use ChatGPT prompt
   - Send polished mockup
   - Update status to "Replied"
2. If lead agrees to project:
   - Update status to "Won"
   - Go to **"💼 Clients"** tab
   - Fill in: Package, Price, Paid, Deadline, Notes

#### Step 8: Repeat
1. Search different city or niche
2. Build pipeline of leads
3. Track conversion rate in Follow-ups tab
4. Adjust templates based on what works

---

## TIPS & BEST PRACTICES

### Searching:
- Start with Overture Maps (free, no key)
- Use radius 10-20 km for cities, 5-10 km for towns
- Search multiple cities with semicolon: "Leeds; Bradford"
- Skip chains/franchises (they're not your clients)
- Check "Only show leads never found before" to find new businesses

### Contacting:
- **ALWAYS verify** before contacting (Map + Google links)
- Call or WhatsApp first for sole traders (email is riskier)
- Don't send more than 15 WhatsApp messages per day
- Include opt-out line in every message
- Stop immediately when someone asks
- Best time to call: 9 AM - 5 PM local time

### Mockups:
- Use instant template for quick results
- Use AI generator for leads who replied (saves quota)
- Use ChatGPT/Claude prompt for best quality
- Always mark as "SAMPLE DESIGN" (not live website)

### Tracking:
- Update status immediately after contacting
- Set follow-up reminder for 4-7 days
- Monitor reply rate (aim for 10-20%)
- Track which niches convert best

### Templates:
- Personalize greeting with first name if available
- Keep WhatsApp messages short and conversational
- Be polite and professional
- Don't sound like a spam bot
- A/B test different templates

---

## COMMON QUESTIONS

**Q: Why does Overture take 30-50 seconds?**
A: It queries a large S3 dataset with DuckDB, downloading only relevant rows. First search is slow, identical searches are cached for 1 hour.

**Q: Should I use Google Places instead?**
A: Use Google if you have budget and need highest accuracy. Overture is free and good enough for most use cases.

**Q: How many leads should I contact per day?**
A: 10-15 quality contacts is better than 50 rushed ones. Don't exceed 15 WhatsApp messages per day to avoid being flagged as spam.

**Q: What if the business already has a website?**
A: Switch to "Has a website — redesign pitch" mode. Evaluate their site, note issues, pitch a redesign.

**Q: Can I export data to Excel?**
A: Yes, use the Downloads tab to export CSV files that open in Excel.

**Q: How do I backup my data?**
A: Click "💾 Prepare backup (.zip)" in the sidebar. Download the ZIP file regularly.

**Q: What if I lose my data?**
A: Restore by copying the backup ZIP files back to the project folder (leads.db, cache.json, clients.json, outreach_settings.json).

**Q: Can I use this for multiple countries?**
A: Yes, change "Target country" in the search card. Overture and Geoapify work worldwide.

**Q: Is the data legal to use?**
A: Yes, all data sources use legal APIs or open data licenses. See README_DETAILED.md for details.

**Q: How accurate is the data?**
A: Google Places is most accurate. Overture/Geoapify can be outdated. Always verify before contacting.

---

## SUMMARY

The Data Scalper frontend is designed to be simple and efficient:

1. **Search** → Find businesses needing websites
2. **Verify** → Confirm they're real and need a website
3. **Contact** → Send personalized messages
4. **Follow up** → Track responses and follow-ups
5. **Convert** → Turn interested leads into clients
6. **Repeat** → Build your client base

The key is to **verify before contacting** and **be respectful** in your outreach. This tool helps you find opportunities, but your professionalism closes the deal.
