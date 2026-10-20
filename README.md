# SocraticAITutor

## 🎓 AI Personal Tutor

A full-stack Generative AI web application that teaches using the **Socratic method** — guiding students to discover answers through questions rather than just handing them solutions.

> **"Think with AI, not instead of AI."**

---

## Features

| Feature | Description |
|---|---|
| 🤖 Socratic AI Tutor | AI that teaches through guided questions, not direct answers |
| 💡 Progressive Hints | 3-level hint system (Concept → Method → Detailed) |
| 🧠 Learning Memory | Remembers your last session and continues from where you left off |
| 📊 Progress Tracking | Visual progress bars per topic, hint usage tracking |
| 📝 Session Summaries | AI-generated summaries at the end of each session |
| 🔍 Topic Detection | Auto-detects what you're learning from your questions |
| 🛡️ Admin Dashboard | Full analytics, student management, session viewer |
| 🔐 JWT Auth | Secure login/register for students and admins |

---

## Tech Stack

- **Backend**: FastAPI + Python + SQLite
- **Frontend**: HTML + CSS + Vanilla JavaScript
- **AI**: OpenRouter API (free models)
- **Auth**: JWT with bcrypt password hashing

---

## Project Structure

```
AI-Personal-Tutor/
├── backend/
│   ├── main.py          ← All API routes (FastAPI)
│   ├── ai_helper.py     ← AI prompts, OpenRouter calls, topic detection
│   ├── tutor.db         ← SQLite database (auto-created on startup)
│   ├── requirements.txt
│   └── .env.example     ← Copy to .env and fill in your keys
│
├── frontend/
│   ├── index.html       ← Login + Register page
│   ├── dashboard.html   ← Student dashboard (chat, progress, history)
│   ├── admin.html       ← Admin dashboard (analytics, students, sessions)
│   ├── style.css        ← All styles (dark theme)
│   └── app.js           ← Shared utilities (API calls, auth, toasts)
│
└── README.md
```

---

## Setup Instructions

### Step 1 — Get an OpenRouter API Key

1. Go to [https://openrouter.ai](https://openrouter.ai) and create a free account
2. Go to **Keys** → **Create Key**
3. Copy your API key (it starts with `sk-or-v1-...`)

The app uses `meta-llama/llama-3.1-8b-instruct:free` which is completely free.

---

### Step 2 — Set Up the Backend

```bash
# Navigate to the backend folder
cd AI-Personal-Tutor/backend

# Create and activate a virtual environment
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Create your environment file
cp .env.example .env
```

Edit `.env` and fill in your values:

```env
OPENROUTER_API_KEY=sk-or-v1-your-key-here
JWT_SECRET=choose-any-random-string-here-make-it-long
```

---

### Step 3 — Run the Backend

```bash
uvicorn main:app --reload
```

You should see:
```
✅ Database initialized. Default admin: admin@tutor.com / admin123
INFO:     Uvicorn running on http://127.0.0.1:8000
```

The API documentation is available at: http://localhost:8000/docs

---

### Step 4 — Open the Frontend

Open `frontend/index.html` in your browser.

> **Tip**: If you hit CORS issues, use VS Code's **Live Server** extension or run:
> ```bash
> cd frontend
> python -m http.server 5500
> ```
> Then open `http://localhost:5500`

---

## Default Admin Account

| Field | Value |
|---|---|
| Email | `admin@tutor.com` |
| Password | `admin123` |

**Change this password** after your first login by modifying the database or adding a change-password API route.

---

## How to Use

### As a Student
1. Register at `index.html`
2. Log in to reach your dashboard
3. Type a question in the chat — e.g. *"Explain Python loops"*
4. The AI will guide you with questions instead of directly answering
5. If stuck, click a **Hint** button (Level 1 → 2 → 3)
6. When done, click **End Session** to save an AI-generated summary
7. Check **My Progress** for topic-level progress bars

### As an Admin
1. Click **Admin** on the login page
2. Log in with `admin@tutor.com` / `admin123`
3. View overall stats, all students, per-topic progress, and session history

---

## API Reference

### Authentication
| Method | Endpoint | Description |
|---|---|---|
| POST | `/register` | Create a student account |
| POST | `/login` | Login, returns JWT token |
| POST | `/logout` | Client-side logout |

### AI
| Method | Endpoint | Description |
|---|---|---|
| POST | `/chat` | Send a message, get a Socratic response |
| POST | `/hint` | Get a progressive hint (level 1/2/3) |

### Student
| Method | Endpoint | Description |
|---|---|---|
| GET | `/progress` | Get topic progress |
| GET | `/history` | Get recent chat history |
| GET | `/summary` | Get past session summaries |
| POST | `/summary/generate` | Generate + save a session summary |

### Admin (requires admin JWT)
| Method | Endpoint | Description |
|---|---|---|
| GET | `/admin/users` | List all students |
| GET | `/admin/progress` | All student progress by topic |
| GET | `/admin/sessions` | All sessions with summaries |
| GET | `/admin/analytics` | Platform-wide statistics |

---

## Deployment

### Deploy Backend (Railway / Render)

**Railway**:
1. Push your `backend/` folder to a GitHub repo
2. Connect it to [Railway](https://railway.app)
3. Set environment variables: `OPENROUTER_API_KEY`, `JWT_SECRET`
4. Railway auto-detects FastAPI and runs `uvicorn main:app --host 0.0.0.0`

**Render**:
1. Create a new **Web Service** on [Render](https://render.com)
2. Connect your GitHub repo
3. Build command: `pip install -r requirements.txt`
4. Start command: `uvicorn main:app --host 0.0.0.0 --port $PORT`
5. Add environment variables in the Render dashboard

---

### Deploy Frontend (Netlify / GitHub Pages)

1. Update `API_BASE` in `frontend/app.js` to your deployed backend URL:
   ```js
   const API_BASE = "https://your-backend.railway.app";
   ```
2. Drag and drop your `frontend/` folder to [Netlify Drop](https://app.netlify.com/drop)
3. Done — your frontend is live!

---

## Customizing the AI Model

Edit `ai_helper.py` to switch to a different model:

```python
# Free models on OpenRouter:
MODEL = "openrouter/free"
MODEL = "cohere/north-mini-code:free"
MODEL = "liquid/lfm-2.5-1.2b-instruct:free"
```

See all free models at: https://openrouter.ai/models?q=free

---

## Adding a New Topic

Edit the `TOPIC_KEYWORDS` dictionary in `ai_helper.py`:

```python
TOPIC_KEYWORDS = {
    "Your New Topic": ["keyword1", "keyword2", "keyword3"],
    ...
}
```

---

## Day-by-Day Build Plan (10 Days)

| Day | Task |
|---|---|
| 1 | Set up project structure, install dependencies |
| 2 | Build database schema and init logic in `main.py` |
| 3 | Implement register/login/JWT auth routes |
| 4 | Build `ai_helper.py` — prompts + OpenRouter integration |
| 5 | Build `/chat` and `/hint` routes |
| 6 | Build `/progress`, `/history`, `/summary` routes |
| 7 | Build admin routes (`/admin/*`) |
| 8 | Build frontend: `index.html` (login/register) |
| 9 | Build frontend: `dashboard.html` (chat, progress, history) |
| 10 | Build frontend: `admin.html`, test everything, deploy |

---

## License

MIT — free to use for learning and projects.
