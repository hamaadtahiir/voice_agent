# Inbound Bot

AI-powered inbound lead qualification and scheduling system for high-value service industries (roofing, landscaping, HVAC, medical, legal, etc.). Acts as a 24/7 digital receptionist: qualifies leads, books appointments on Google Calendar, notifies the business team, and sends reminders.

## Features

- **Multi-channel inbound**:
  - **Web chat widget** -- embeddable `<script>` tag, WebSocket-based, works on any website
  - **AI phone calls** -- inbound call handling via Vapi.ai (voice AI with tool calling)
  - **WhatsApp** -- Meta Cloud API integration with media support
  - **Email** -- inbound email processing via Resend webhooks
- **Multi-tenant**: One system serves multiple businesses, each with their own config
- **AI Conversations**: LangGraph-powered conversation flow using GPT-4.1-nano
- **Lead Qualification**: Location check, pain point identification, service matching, scoring (0-100)
- **Calendar Integration**: Google Calendar OAuth, availability checking, appointment booking
- **Instant Quotes**: Price range estimates for quotable services
- **Notifications**: Slack + email + SMS alerts to business teams on new bookings
- **Reminders**: Automated 24h and 1h appointment reminders via SMS/email
- **Re-engagement**: Auto-detect dropped conversations, send SMS nudges
- **Admin Panel**: Dashboard, business onboarding wizard, lead/appointment management

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | FastAPI (Python 3.11+) |
| Database | SQLite (dev/demo) / PostgreSQL (prod) |
| ORM | SQLAlchemy 2.0 async + Alembic |
| AI/LLM | OpenAI GPT-4.1-nano |
| Conversation | LangGraph (state machine) |
| Calendar | Google Calendar API |
| Phone | Vapi.ai |
| WhatsApp | Meta Cloud API |
| SMS | Twilio |
| Email | Resend |
| Admin UI | Jinja2 + htmx + Tailwind CSS |
| Background Jobs | APScheduler |

---

## Local Development Setup

### Prerequisites

- Python 3.11+
- An OpenAI API key

### 1. Create virtual environment

```bash
python -m venv venv
source venv/bin/activate  # macOS/Linux
# or: venv\Scripts\activate  # Windows
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure environment

```bash
cp .env.example .env
```

Edit `.env` and set these required values:

```env
OPENAI_API_KEY=sk-your-actual-openai-key

# Generate encryption key:
# python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
ENCRYPTION_KEY=your-generated-fernet-key

ADMIN_JWT_SECRET=any-random-secret-string
```

All other values (Twilio, Google, WhatsApp, Vapi) are optional and only needed for their respective features.

### 4. Seed the database

```bash
PYTHONPATH=. python scripts/seed_dev_data.py
```

This creates:
- **Admin account**: `admin@inbound-bot.com` / `admin123`
- **Apex Roofing Co** (slug: `apex-roofing`) -- sample roofing business with 5 services
- **Green Valley Landscaping** (slug: `green-valley`) -- sample landscaping business with 4 services

### 5. Start the server

```bash
PYTHONPATH=. uvicorn app.main:app --reload --port 8000
```

### 6. Verify it's running

- **API docs**: http://localhost:8000/docs
- **Health check**: http://localhost:8000/health
- **Admin panel**: http://localhost:8000/admin/login

## Testing Each Channel

### Web Chat Widget

Open `test_chat.html` in your browser (just double-click the file). It simulates a roofing business website with the chat widget embedded.

The widget connects to `ws://localhost:8000/ws/chat/apex-roofing`, so make sure the server is running.

**Sample conversation flow:**

1. Bot greets you with the business welcome message
2. Say something like "I need help with my roof"
3. Bot asks for your zip code -- try `10001` (in service area) or `90210` (out of area)
4. Bot asks about your issue -- describe a roofing problem
5. Bot identifies the service, offers a quote range
6. Bot helps schedule an appointment (requires Google Calendar configured)

### CLI Conversation Tester

For quick testing without a browser:

```bash
PYTHONPATH=. python scripts/test_conversation.py apex-roofing
```

This opens an interactive terminal session with the bot.

### Inbound Phone Calls (Vapi)

The system handles AI-powered inbound phone calls via [Vapi.ai](https://vapi.ai/). When a customer calls, Vapi runs the voice conversation and calls back to our webhook for tool execution (checking availability, booking appointments). After the call ends, the transcript and lead data are saved automatically.

**How it works:**

1. Customer calls the Vapi phone number assigned to a business
2. Vapi sends an `assistant-request` to `POST /webhooks/vapi` -- our server returns the AI assistant config (system prompt, voice, tools)
3. During the call, Vapi sends `function-call` webhooks when the AI needs to check availability or book an appointment -- our server executes these against Google Calendar and the database
4. When the call ends, Vapi sends an `end-of-call-report` -- our server creates the lead record, scores it, and saves the full transcript

**To test inbound calls:**

1. Sign up at [vapi.ai](https://vapi.ai/) and get an API key
2. Buy or assign a phone number in the Vapi dashboard
3. Create an assistant in Vapi with **Server URL** set to `https://your-deployed-url/webhooks/vapi` (must be publicly accessible -- use ngrok for local testing: `ngrok http 8000`)
4. Set `VAPI_API_KEY` in `.env`
5. In the admin panel, set the `vapi_assistant_id` and `vapi_phone_number_id` on the business record
6. Call the Vapi phone number -- the AI answers, qualifies the caller, and books an appointment
7. Check the admin panel -- the lead and transcript appear under Leads

> **Note**: Vapi handles the voice AI conversation itself (speech-to-text, LLM, text-to-speech). Our server only provides the tool implementations and stores the results. This is different from the web chat/WhatsApp channels where our LangGraph engine runs the full conversation.

### WhatsApp

1. Expose your server publicly (deploy to cloud or use `ngrok http 8000`)
2. Configure the webhook URL in your Meta Business App: `https://your-url/webhooks/whatsapp`
3. Set `WHATSAPP_VERIFY_TOKEN` in `.env` to match what you configure in Meta
4. Send a WhatsApp message to the business number -- the bot responds through the same qualification flow as web chat

### Email

1. Configure an inbound email provider (e.g., Resend) to forward emails to `POST https://your-url/webhooks/email`
2. Incoming emails are routed through the conversation engine
3. Replies are sent back via the Resend API

## Admin Panel

Login at http://localhost:8000/admin/login with `admin@inbound-bot.com` / `admin123`.

### Pages

- **Dashboard**: Lead stats, conversion funnel, channel breakdown charts, upcoming appointments
- **Businesses**: List, create, and edit businesses with a 6-tab configuration wizard (Basic Info, Service Areas, Services, Business Hours, Branding, Integrations)
- **Leads**: Filterable table with score, status, channel. Click into a lead to see the full conversation transcript
- **Appointments**: List with status management (confirm, complete, cancel, no-show)

## Running Tests

```bash
pip install -r requirements-dev.txt
PYTHONPATH=. pytest tests/ -v
```

---

## Cloud Deployment (Full Demo with Chat + Phone Calls)

Pick one platform below. Each guide is **end-to-end**: from zero to a fully working demo with chat widget, AI phone calls, calendar booking, and admin panel.

**Prerequisites for all options:**
- An [OpenAI API key](https://platform.openai.com/api-keys)
- Generate an encryption key: `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`
- Pick a random string for `ADMIN_JWT_SECRET` (e.g., `mysecretkey123`)
- A [Vapi.ai](https://vapi.ai/) account for phone calls (free trial, ~$10 credit)
- (Optional) [Google Cloud](https://console.cloud.google.com/) project for calendar integration

---

### Option A: Railway (Easiest -- ~20 minutes total)

**Cost**: $5/month hobby plan + Vapi usage (~$0.05/min for calls)

#### A1. Deploy the app

```bash
# Install Railway CLI
brew install railway          # macOS
# npm install -g @railway/cli  # or via npm

# Login
railway login

# Initialize project (from the project directory)
cd /path/to/inbound_bot
railway init
# Follow prompts to create a new project

# Deploy
railway up
# Wait for build to complete (~2-3 minutes first time)
```

#### A2. Add persistent volume

In the Railway dashboard: select your service > **Settings** > **Volumes** > **New Volume**:
- **Mount path**: `/data`

#### A3. Get your public URL

After deploy, find your URL in the Railway dashboard under your service's **Settings** tab (e.g., `https://inbound-bot-production.up.railway.app`). You'll need this for every step below -- we'll call it `YOUR_APP_URL`.

#### A4. Set environment variables

Go to [railway.com](https://railway.com) > select your service > **Variables** tab. Add all of these:

| Variable | Value |
|---|---|
| `OPENAI_API_KEY` | `sk-your-openai-key` |
| `ENCRYPTION_KEY` | (the Fernet key you generated above) |
| `ADMIN_JWT_SECRET` | (your random secret string) |
| `DATABASE_URL` | `sqlite+aiosqlite:////data/inbound_bot.db` |
| `BASE_URL` | `https://YOUR_APP_URL` (your Railway URL with https) |
| `DEBUG` | `true` |
| `VAPI_API_KEY` | (from Vapi dashboard, see step A7) |

> **Tip**: You can paste a full `.env` file using the "RAW Editor" in the Variables tab.

Railway auto-redeploys when variables change. Wait for the deploy to finish.

#### A5. Seed the database

```bash
railway shell
python scripts/seed_dev_data.py
exit
```

This creates:
- **Admin account**: `admin@inbound-bot.com` / `admin123`
- **Apex Roofing Co** (slug: `apex-roofing`) with 5 services
- **Green Valley Landscaping** (slug: `green-valley`) with 4 services

#### A6. Verify everything is running

```bash
# Health check
curl https://YOUR_APP_URL/health
# Expected: {"status":"healthy","service":"inbound-bot"}
```

Open in browser:
- **Admin panel**: `https://YOUR_APP_URL/admin/login` -- login with `admin@inbound-bot.com` / `admin123`
- **API docs**: `https://YOUR_APP_URL/docs`

#### A7. Set up AI phone calls (Vapi)

**Create Vapi account and phone number:**

1. Sign up at [vapi.ai](https://vapi.ai/) (free trial includes ~$10 credit, enough for ~200 min)
2. Copy your **API key** from the Vapi dashboard -- go back to Railway and add it as `VAPI_API_KEY` in Variables
3. Go to **Phone Numbers** > **Buy Number** -- pick a US number
4. Note the **Phone Number ID** on the number's detail page

**Create assistant pointing to your server:**

1. Go to **Assistants** > **Create Assistant**
2. Set **Server URL** to: `https://YOUR_APP_URL/webhooks/vapi`
3. Under **Server Events**, enable: `assistant-request`, `function-call`, `end-of-call-report`
4. Under **Advanced**: leave **First message** empty (our server provides it dynamically), set **Max duration** to 600 seconds
5. **IMPORTANT**: Leave the **System Prompt** field empty in the Vapi dashboard -- the server provides it dynamically based on the business configuration. If you paste a prompt here, it will override the server's dynamic prompt.
6. Save -- note the **Assistant ID**

**Connect phone number to assistant:**

1. Go to **Phone Numbers** > click your number
2. Set **Inbound Assistant** to the assistant you just created
3. Save

**Link Vapi to your business record:**

```bash
# Get admin token
TOKEN=$(curl -s -X POST https://YOUR_APP_URL/api/admin/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@inbound-bot.com","password":"admin123"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

# List businesses to get the ID
curl -s https://YOUR_APP_URL/api/businesses \
  -H "Authorization: Bearer $TOKEN" \
  | python3 -c "import sys,json; [print(b['id'], b['slug']) for b in json.load(sys.stdin)]"

# Update Apex Roofing with your Vapi IDs (replace the three ALL-CAPS values)
curl -X PUT https://YOUR_APP_URL/api/businesses/BUSINESS_ID \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "vapi_phone_number_id": "YOUR_VAPI_PHONE_NUMBER_ID",
    "vapi_assistant_id": "YOUR_VAPI_ASSISTANT_ID"
  }'
```

Or use the admin panel: **Businesses** > **Apex Roofing** > **Integrations** tab > paste the Vapi IDs.

#### A8. Connect Google Calendar (optional, recommended)

This lets the bot check real availability and create events during chat and phone demos.

1. Go to [Google Cloud Console](https://console.cloud.google.com/) > **APIs & Services** > **Credentials**
2. Create an **OAuth 2.0 Client ID** (Web application type)
3. Add redirect URI: `https://YOUR_APP_URL/api/businesses/oauth/google/callback`
4. Enable the **Google Calendar API** in the API Library
5. Add to Railway Variables:
   ```
   GOOGLE_CLIENT_ID=your-client-id.apps.googleusercontent.com
   GOOGLE_CLIENT_SECRET=your-client-secret
   GOOGLE_REDIRECT_URI=https://YOUR_APP_URL/api/businesses/oauth/google/callback
   ```
6. In admin panel: **Businesses** > **Apex Roofing** > **Integrations** > **Connect Google Calendar**
7. Complete the OAuth flow

#### A9. Set up notifications (optional)

Add to Railway Variables for each service you want:

| Service | Variables to add | Then configure on business |
|---|---|---|
| **Slack** | (none) | Add webhook URL in admin > Integrations |
| **Email** | `RESEND_API_KEY` | Add notification emails in admin > Integrations |
| **SMS** | `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_PHONE_NUMBER` | Add notification phone in admin > Integrations |

#### A10. Test the full demo

**Test chat widget** -- create an HTML file and open it in your browser:

```html
<!DOCTYPE html>
<html>
<head><title>Chat Demo</title></head>
<body>
  <h1>Apex Roofing Co</h1>
  <p>Click the chat button in the bottom-right corner.</p>
  <script src="https://YOUR_APP_URL/widget/apex-roofing.js" async></script>
</body>
</html>
```

Chat demo script:
1. Click the chat bubble -- bot greets you
2. Type: "I need help with my roof" -- bot asks for location
3. Type: `10001` -- bot confirms in-service-area
4. Type: "I have a leak in my ceiling" -- bot identifies service, offers quote
5. Bot walks through scheduling (books on Google Calendar if connected)

**Test phone calls** -- call the Vapi phone number:
1. AI answers: "Hello! Thank you for calling Apex Roofing..."
2. Say: "I have water coming through my ceiling after the storm"
3. AI asks for name, zip code, identifies the service
4. AI offers to schedule an appointment
5. After hanging up, check admin panel -- lead appears with transcript, score, channel = "phone"

**Verify in admin panel** (`https://YOUR_APP_URL/admin/dashboard`):
- Leads from both chat and phone appear in the lead list
- Appointments show up with correct status
- Dashboard charts reflect the new data

#### A11. Redeploy after code changes

```bash
railway up
```

---

### Option B: Render (~25 minutes total)

**Cost**: $7/month starter plan + Vapi usage (~$0.05/min for calls)

A `render.yaml` is included in the project.

#### B1. Deploy the app

1. Push your code to a **GitHub** or **GitLab** repository
2. Go to [dashboard.render.com](https://dashboard.render.com) > **New** > **Blueprint**
3. Connect your repo -- Render auto-detects `render.yaml`
4. Set secret environment variables in the dashboard:

   | Variable | Value |
   |---|---|
   | `OPENAI_API_KEY` | `sk-your-openai-key` |
   | `ENCRYPTION_KEY` | (your generated Fernet key) |
   | `ADMIN_JWT_SECRET` | (your random secret string) |
   | `BASE_URL` | `https://inbound-bot.onrender.com` (update after deploy with actual URL) |
   | `VAPI_API_KEY` | (from Vapi dashboard, see step B4) |

5. Click **Apply** -- Render builds and deploys (~3-5 minutes)

> **Manual setup** (without render.yaml): **New** > **Web Service** > Docker runtime > Starter plan ($7/mo) > add disk at `/data` (1 GB) > add env vars including `DATABASE_URL=sqlite+aiosqlite:////data/inbound_bot.db`

#### B2. Seed the database

Go to your service > **Shell** tab:
```bash
python scripts/seed_dev_data.py
```

Creates admin (`admin@inbound-bot.com` / `admin123`) and two sample businesses.

#### B3. Verify

- **Health**: `curl https://YOUR_APP_URL/health`
- **Admin panel**: `https://YOUR_APP_URL/admin/login`
- **API docs**: `https://YOUR_APP_URL/docs`

#### B4. Set up AI phone calls (Vapi)

1. Sign up at [vapi.ai](https://vapi.ai/), copy your API key, add it as `VAPI_API_KEY` in Render environment
2. **Phone Numbers** > **Buy Number** > note the **Phone Number ID**
3. **Assistants** > **Create Assistant**:
   - **Server URL**: `https://YOUR_APP_URL/webhooks/vapi`
   - Enable events: `assistant-request`, `function-call`, `end-of-call-report`
   - Leave **First message** empty, set **Max duration** = 600s
   - **IMPORTANT**: Leave the **System Prompt** field empty -- the server provides it dynamically based on the business
   - Save, note the **Assistant ID**
4. **Phone Numbers** > your number > set **Inbound Assistant** > save
5. Link to business:
   ```bash
   TOKEN=$(curl -s -X POST https://YOUR_APP_URL/api/admin/login \
     -H "Content-Type: application/json" \
     -d '{"email":"admin@inbound-bot.com","password":"admin123"}' \
     | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

   # Get business ID
   curl -s https://YOUR_APP_URL/api/businesses \
     -H "Authorization: Bearer $TOKEN" \
     | python3 -c "import sys,json; [print(b['id'], b['slug']) for b in json.load(sys.stdin)]"

   # Update business (replace BUSINESS_ID and Vapi IDs)
   curl -X PUT https://YOUR_APP_URL/api/businesses/BUSINESS_ID \
     -H "Authorization: Bearer $TOKEN" \
     -H "Content-Type: application/json" \
     -d '{"vapi_phone_number_id": "YOUR_ID", "vapi_assistant_id": "YOUR_ID"}'
   ```
   Or use admin panel: **Businesses** > **Apex Roofing** > **Integrations** tab.

#### B5. Connect Google Calendar (optional)

1. [Google Cloud Console](https://console.cloud.google.com/) > create OAuth 2.0 Client ID
2. Redirect URI: `https://YOUR_APP_URL/api/businesses/oauth/google/callback`
3. Enable Google Calendar API
4. Add to Render environment: `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REDIRECT_URI`
5. Admin panel: **Businesses** > **Apex Roofing** > **Integrations** > **Connect Google Calendar**

#### B6. Set up notifications (optional)

Add to Render environment: `RESEND_API_KEY` (email), `TWILIO_ACCOUNT_SID` + `TWILIO_AUTH_TOKEN` + `TWILIO_PHONE_NUMBER` (SMS). Configure webhook URLs and notification contacts on the business via admin panel.

#### B7. Test the full demo

Same as Option A, Step A10 -- test chat widget with embedded script tag, test phone by calling the Vapi number, verify leads appear in admin panel.

**Notes**: Render auto-deploys on `git push`. Starter plan may have ~15-30s cold starts after inactivity.

---

### Option C: Fly.io (~25 minutes total)

**Cost**: Usage-based (~$3-5/month) + Vapi usage. Free trial: 2 VM hours or 7 days.

A `fly.toml` with SQLite volume mount is included.

#### C1. Deploy the app

```bash
# Install flyctl
brew install flyctl            # macOS
# curl -L https://fly.io/install.sh | sh  # Linux

# Sign up / login
fly auth signup   # new account
# fly auth login  # existing account

# Launch (from the project directory)
cd /path/to/inbound_bot
fly launch
# Detects fly.toml and Dockerfile
# Choose an app name or accept the default
# Select region (iad = US East)
# Say YES to deploy now

# Create persistent volume for SQLite (if not created during launch)
fly volumes create inbound_bot_data --size 1 --region iad

# Set secrets
fly secrets set \
  OPENAI_API_KEY="sk-your-key" \
  ENCRYPTION_KEY="your-fernet-key" \
  ADMIN_JWT_SECRET="your-random-secret" \
  BASE_URL="https://your-app.fly.dev"

# Deploy
fly deploy
```

#### C2. Seed the database

```bash
fly ssh console -C "python scripts/seed_dev_data.py"
```

Creates admin (`admin@inbound-bot.com` / `admin123`) and two sample businesses.

#### C3. Verify

```bash
fly open  # opens https://your-app.fly.dev in browser
```

- **Health**: `curl https://YOUR_APP_URL/health`
- **Admin panel**: `https://YOUR_APP_URL/admin/login`
- **API docs**: `https://YOUR_APP_URL/docs`

#### C4. Set up AI phone calls (Vapi)

1. Sign up at [vapi.ai](https://vapi.ai/), copy your API key:
   ```bash
   fly secrets set VAPI_API_KEY="your-vapi-api-key"
   ```
2. **Phone Numbers** > **Buy Number** > note the **Phone Number ID**
3. **Assistants** > **Create Assistant**:
   - **Server URL**: `https://YOUR_APP_URL/webhooks/vapi`
   - Enable events: `assistant-request`, `function-call`, `end-of-call-report`
   - Leave **First message** empty, set **Max duration** = 600s
   - **IMPORTANT**: Leave the **System Prompt** field empty -- the server provides it dynamically based on the business
   - Save, note the **Assistant ID**
4. **Phone Numbers** > your number > set **Inbound Assistant** > save
5. Link to business:
   ```bash
   TOKEN=$(curl -s -X POST https://YOUR_APP_URL/api/admin/login \
     -H "Content-Type: application/json" \
     -d '{"email":"admin@inbound-bot.com","password":"admin123"}' \
     | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

   curl -s https://YOUR_APP_URL/api/businesses \
     -H "Authorization: Bearer $TOKEN" \
     | python3 -c "import sys,json; [print(b['id'], b['slug']) for b in json.load(sys.stdin)]"

   curl -X PUT https://YOUR_APP_URL/api/businesses/BUSINESS_ID \
     -H "Authorization: Bearer $TOKEN" \
     -H "Content-Type: application/json" \
     -d '{"vapi_phone_number_id": "YOUR_ID", "vapi_assistant_id": "YOUR_ID"}'
   ```
   Or use admin panel: **Businesses** > **Apex Roofing** > **Integrations** tab.

#### C5. Connect Google Calendar (optional)

1. [Google Cloud Console](https://console.cloud.google.com/) > create OAuth 2.0 Client ID
2. Redirect URI: `https://YOUR_APP_URL/api/businesses/oauth/google/callback`
3. Enable Google Calendar API
4. ```bash
   fly secrets set \
     GOOGLE_CLIENT_ID="your-client-id.apps.googleusercontent.com" \
     GOOGLE_CLIENT_SECRET="your-client-secret" \
     GOOGLE_REDIRECT_URI="https://YOUR_APP_URL/api/businesses/oauth/google/callback"
   ```
5. Admin panel: **Businesses** > **Apex Roofing** > **Integrations** > **Connect Google Calendar**

#### C6. Set up notifications (optional)

```bash
# Email notifications
fly secrets set RESEND_API_KEY="re_your-key"

# SMS notifications
fly secrets set \
  TWILIO_ACCOUNT_SID="your-sid" \
  TWILIO_AUTH_TOKEN="your-token" \
  TWILIO_PHONE_NUMBER="+15551234567"
```

Then configure webhook URLs and notification contacts on the business via admin panel.

#### C7. Test the full demo

Same as Option A, Step A10 -- test chat widget with embedded script tag, test phone by calling the Vapi number, verify leads appear in admin panel.

**Useful commands:**
```bash
fly logs              # View live logs
fly status            # App status
fly ssh console       # SSH into running machine
fly secrets list      # List configured secrets
fly deploy            # Redeploy after changes
```

**Notes**: `fly.toml` sets `min_machines_running = 1` to avoid cold starts. Set to `0` to save money when not demoing.

---

### Demo Day Checklist

Before the client demo, verify everything works:

- [ ] `https://YOUR_APP_URL/health` returns healthy
- [ ] Admin login works at `https://YOUR_APP_URL/admin/login`
- [ ] Chat widget loads on test page (check browser console for WebSocket errors)
- [ ] Chat conversation flows through qualification (test with zip `10001`)
- [ ] Call the Vapi phone number -- AI answers with business name
- [ ] Phone conversation captures lead info (check admin panel after call)
- [ ] Google Calendar shows availability and creates events (if connected)
- [ ] Slack/email notifications fire on new bookings (if configured)

### What to Show Clients

1. **Chat widget embed** -- "Add one line of code to your website and you have a 24/7 AI receptionist"
2. **Live phone call** -- call the number during the demo, let them hear the AI
3. **Admin panel** -- show leads appearing in real-time with scores, transcripts, and status
4. **Multi-business** -- switch between Apex Roofing and Green Valley Landscaping to show multi-tenant
5. **Appointment booking** -- show the Google Calendar event created by the bot
6. **Analytics dashboard** -- show the lead funnel and channel breakdown charts

### Platform Comparison

| Feature | Railway | Render | Fly.io |
|---|---|---|---|
| **Setup time** | ~5 min | ~10 min | ~10 min |
| **Cost** | $5/mo | $7/mo | ~$3-5/mo |
| **Deploy method** | CLI (`railway up`) | Git push or dashboard | CLI (`fly deploy`) |
| **Persistent disk** | Dashboard config | Built-in with render.yaml | Volume via CLI |
| **WebSocket** | Yes | Yes | Yes |
| **Custom domain** | Yes | Yes | Yes |
| **Auto-deploy on push** | Yes (with GitHub link) | Yes | Yes (with GitHub link) |
| **Cold starts** | Minimal | 15-30s on starter | ~5s if machine is stopped |
| **Shell access** | `railway shell` | Dashboard shell tab | `fly ssh console` |

---

## Docker (Local / Self-Hosted)

```bash
docker compose up --build
```

This starts the app + PostgreSQL. Access at http://localhost:8000.

For dev mode with hot reload:

```bash
docker compose -f docker-compose.dev.yml up --build
```

---

## API Endpoints

| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | Health check |
| WS | `/ws/chat/{slug}` | Real-time web chat |
| POST | `/api/admin/login` | Admin JWT auth |
| GET/POST | `/api/businesses` | List/create businesses |
| GET/PUT/DELETE | `/api/businesses/{id}` | Business detail/update/delete |
| GET | `/api/leads` | List leads (filterable) |
| GET | `/api/leads/{id}` | Lead detail |
| GET | `/api/leads/{id}/conversations` | Lead conversation transcript |
| GET/POST | `/api/appointments` | List/create appointments |
| PUT | `/api/appointments/{id}` | Update appointment status |
| GET | `/api/dashboard` | Analytics data |
| GET/POST | `/webhooks/whatsapp` | WhatsApp messages |
| POST | `/webhooks/vapi` | Vapi voice AI |
| POST | `/webhooks/email` | Inbound email |
| GET | `/widget/{slug}.js` | Per-business widget loader |

## Website Integration

Add a single script tag to any website:

```html
<script src="https://your-domain.com/widget/apex-roofing.js" async></script>
```

This creates a floating chat button in the bottom-right corner that opens a full conversation interface.

## Project Structure

```
inbound_bot/
├── app/
│   ├── main.py                  # FastAPI app factory
│   ├── config.py                # Pydantic settings
│   ├── db/                      # Async engine, session, base
│   ├── models/                  # SQLAlchemy ORM (7 models)
│   ├── schemas/                 # Pydantic request/response
│   ├── api/                     # Route handlers (13 modules)
│   ├── services/                # Business logic (9 modules)
│   ├── graph/                   # LangGraph conversation flow
│   ├── widget/                  # Embeddable chat widget
│   └── admin_ui/                # Jinja2 templates + static
├── alembic/                     # Database migrations
├── scripts/                     # Seed data, CLI tester
├── tests/                       # pytest suite
├── test_chat.html               # Widget test page
├── Dockerfile
├── docker-compose.yml
├── fly.toml                     # Fly.io config
├── render.yaml                  # Render config
└── requirements.txt
```

## Optional Integration Setup

### Google Calendar

1. Go to [Google Cloud Console](https://console.cloud.google.com/) > APIs & Services > Credentials
2. Create an OAuth 2.0 Client ID (Web application)
3. Add redirect URI: `https://your-app-url/api/businesses/oauth/google/callback`
4. Enable the Google Calendar API
5. Set `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REDIRECT_URI` in your environment
6. In the admin panel, click "Connect Google Calendar" on a business

### WhatsApp

1. Create a Meta Business App at [developers.facebook.com](https://developers.facebook.com/)
2. Add WhatsApp product, get Phone Number ID and Access Token
3. Set webhook URL to `https://your-app-url/webhooks/whatsapp`
4. Set `WHATSAPP_VERIFY_TOKEN` in your environment, configure on the business record

### Vapi (AI Phone Calls)

Vapi handles the voice conversation (speech-to-text, LLM, text-to-speech). Our server provides tool implementations via webhooks so the AI can check calendar availability and book appointments during the call. After the call, Vapi sends the transcript which we store as a lead.

1. Sign up at [vapi.ai](https://vapi.ai/) and get your API key
2. Buy a phone number in the Vapi dashboard (or port an existing one)
3. Create an assistant -- set **Server URL** to `https://your-app-url/webhooks/vapi`. **Leave the System Prompt field empty** -- the server provides it dynamically based on the business.
4. Set `VAPI_API_KEY` in your environment
5. In the admin panel, edit the business and set `vapi_assistant_id` and `vapi_phone_number_id` to match what's in Vapi
6. Call the phone number -- the AI answers, qualifies the caller, and can book appointments
7. After the call, check the admin panel -- the lead appears with the full transcript

**Webhook events handled:**
- `assistant-request` -- returns dynamic assistant config (system prompt, tools, voice) based on which business the phone number belongs to
- `function-call` -- executes `check_availability` and `book_appointment` tools against Google Calendar
- `end-of-call-report` -- creates lead record, scores it, saves transcript

**Local testing with ngrok:**
```bash
ngrok http 8000
# Copy the https URL, e.g. https://abc123.ngrok.io
# Set it as the Server URL in your Vapi assistant
```

### Twilio (SMS)

1. Sign up at [twilio.com](https://www.twilio.com/)
2. Get Account SID, Auth Token, and a phone number
3. Set `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_PHONE_NUMBER` in your environment
