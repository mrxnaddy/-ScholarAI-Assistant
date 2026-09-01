# 🎓 ScholarAI Assistant

**ScholarAI** is an AI-powered scholarship and student opportunity advisor. It combines a local opportunities database, live web search, and an LLM-driven tool-calling agent to help students discover scholarships, check their eligibility, and find required documents — all through a simple chat interface.

🔗 **Live App:** [scholaraiassistant.streamlit.app](https://scholaraiassistant.streamlit.app/)

---

## ✨ Features

- **💬 AI Advisor Chat** — Ask natural-language questions like *"Find scholarships for my profile and check eligibility"* and get concise, structured markdown answers.
- **🔍 Database Search** — Browse locally stored scholarship opportunities filtered by degree and location.
- **🌐 Live Web Search** — Pulls in fresh, currently active scholarships from the web when the local database has limited options.
- **🔗 URL Extraction** — Can scrape and summarize scholarship details directly from a given webpage link.
- **✅ Eligibility Checker** — Matches a student's profile (degree, CGPA, location) against an opportunity's requirements.
- **📄 Document Checklist** — Lists required documents for a specific scholarship application.
- **🧠 Multi-model fallback** — Automatically switches between available LLM providers/models (Groq, OpenRouter, OpenAI) if one is unavailable.

---

## 🛠️ Tech Stack

| Layer            | Technology                              |
|-------------------|------------------------------------------|
| Frontend          | [Streamlit](https://streamlit.io/)       |
| AI / LLM Agent    | Groq API / OpenRouter / OpenAI (with tool-calling) |
| Backend Logic     | Python                                   |
| Data              | Local database of scholarship opportunities |
| Web Search        | Custom web search integration            |

---

## 📁 Project Structure

```
scholar-ai/
├── frontend/
│   └── app.py                # Streamlit UI (chat, DB browser, web search tabs)
├── backend/
│   ├── agent.py               # Core AI agent — tool calling, prompt, model fallback
│   ├── tools.py                # Scholarship search, eligibility, document tools
│   ├── database.py             # Local opportunities database access
│   └── web_search.py           # Live web search integration
├── .env                        # API keys (not committed)
└── README.md
```

---

## ⚙️ How It Works

1. The **student profile** (degree, CGPA, location) is entered in the sidebar.
2. A query is sent to the **AI Advisor**, which uses an LLM with tool-calling to decide which backend tools to invoke:
   - `search_opportunities` — searches the local database
   - `check_eligibility` — validates a student against an opportunity's criteria
   - `get_required_documents` — returns the application document checklist
   - `search_web` — searches the web for additional/live opportunities
   - `extract_scholarship_details_from_url` — scrapes a specific scholarship page
3. Results are cleaned, formatted, and returned as **concise markdown bullet points** — no filler, no raw JSON, no clutter.

---

## 🚀 Running Locally

### 1. Clone the repository
```bash
git clone https://github.com/<your-username>/scholar-ai.git
cd scholar-ai
```

### 2. Install dependencies
```bash
pip install -r requirements.txt
```

### 3. Set up environment variables
Create a `.env` file in the project root:
```env
GROQ_API_KEY=your_groq_api_key
OPENROUTER_API_KEY=your_openrouter_api_key
OPENAI_API_KEY=your_openai_api_key
```
> Only **one** key is required — the agent automatically picks the first available provider (Groq → OpenRouter → OpenAI).

### 4. Run the app
```bash
streamlit run frontend/app.py
```

The app will open in your browser at `http://localhost:8501`.

---

## 📌 Notes

- The agent enforces **strict output formatting**: no greetings, no filler text, only structured scholarship data (title, summary, deadline, link).
- If the local database has limited results, the agent automatically falls back to live web search.
- Multiple LLM models are tried in sequence if one fails or is decommissioned, ensuring reliability.

---

## 📄 License

This project is open for educational and personal use. Feel free to fork and adapt it.
