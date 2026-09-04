import os
import json
import re
import time
from pathlib import Path
from dotenv import load_dotenv
import streamlit as st
from google import genai
from google.genai import types

from backend.tools import (
    search_opportunities,
    check_eligibility,
    get_required_documents,
    extract_scholarship_details_from_url
)
from backend.web_search import search_web
from backend.database import get_all_opportunities

env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(env_path)

gemini_key = os.getenv("GEMINI_API_KEY")
if not gemini_key:
    try:
        gemini_key = st.secrets.get("GEMINI_API_KEY")
    except Exception:
        pass

if not gemini_key:
    gemini_key = os.getenv("OPENAI_API_KEY")

if gemini_key:
    client = genai.Client(api_key=gemini_key)
else:
    raise RuntimeError("No GEMINI_API_KEY configured in .env or Streamlit secrets.")

# Models ki list jo aik ke baad aik try ki jaye gi
MODELS_TO_TRY = [
    "gemini-3.6-flash"
]
SYSTEM_INSTRUCTIONS = """
You are ScholarAI, a professional scholarship search assistant.

Your ONLY task is to return relevant scholarship opportunities.

STRICT RULES:
1. Do not write greetings, introductions, explanations, conclusions, recommendations, or closing messages.
2. Output ONLY markdown bullet points.
3. Maximum 6 scholarship results.
4. Only show scholarships relevant to the student's profile and query.
5. Never invent scholarship names, deadlines, requirements, eligibility, benefits, or URLs.
6. Use only information provided by the available tools or verified sources.
7. Prefer the official scholarship/provider URL when available.
8. Never modify or create URLs.
9. If the deadline is not verified, write exactly "Not verified".
10. Do not show scholarships where the student clearly fails the available eligibility criteria.
11. Do not include required documents, eligibility explanations, provider names, benefits, locations, or application instructions unless the user specifically asks.
12. Summary must be one short sentence of maximum 15 words.
13. Each result MUST follow exactly this format:

- **Title:** Scholarship Name | **Summary:** Short summary | **Deadline:** Exact deadline | **Link:** [Official Source](URL)

14. No headings.
15. No tables.
16. No JSON.
17. No code blocks.
18. Nothing before or after the bullet points.
19. If no relevant verified scholarship is found, output exactly:

- No matching opportunities found.
"""

def sanitize_output(text: str) -> str:
    if not text:
        return "- No matching opportunities found."

    clean = re.sub(r'<think>.*?</think>', '', text, flags=re.IGNORECASE | re.DOTALL)
    clean = re.sub(r'<tool_call>.*?</tool_call>', '', clean, flags=re.IGNORECASE | re.DOTALL)
    clean = re.sub(r'</?tool_call>|</?think>', '', clean, flags=re.IGNORECASE)
    clean = clean.strip()
    return clean or "- No matching opportunities found."

def ask_ai(message: str, student: dict = None) -> str:
    if not student:
        student = {}

    if not student.get("name"):
        student["name"] = "Nadir Hussain"
    if not student.get("degree"):
        student["degree"] = "BSCS"
    if not student.get("location"):
        student["location"] = "Pakistan"

    all_opportunities = get_all_opportunities()

    def tool_search_opportunities(degree: str = "BSCS", location: str = "Pakistan"):
        """Search local database for scholarship opportunities matching degree and location."""
        raw_res = search_opportunities(degree=degree, location=location)
        return raw_res if raw_res else "No matching local opportunities found."

    def tool_check_eligibility(opportunity_id: str):
        """Check if a student meets criteria for an opportunity ID."""
        opp = next((i for i in all_opportunities if i["id"] == opportunity_id), None)
        if not opp:
            return {"error": "Opportunity not found"}
        return check_eligibility(student, opp)

    def tool_get_required_documents(opportunity_id: str):
        """Get required documents for a specific scholarship opportunity ID."""
        opp = next((i for i in all_opportunities if i["id"] == opportunity_id), None)
        if not opp:
            return {"error": "Opportunity not found"}
        return get_required_documents(opp)

    def tool_search_web(query: str):
        """Search web for active scholarships if database has few options."""
        raw_res = search_web(query)
        return raw_res if raw_res else "No web results found."

    tools_list = [
        tool_search_opportunities,
        tool_check_eligibility,
        tool_get_required_documents,
        tool_search_web
    ]

    user_prompt = f"Student Profile: {json.dumps(student)}\nUser Query: {message}"

    last_error = ""
    # Models loop: aik model fail ho toh agla try hoga
    for model_name in MODELS_TO_TRY:
        max_retries = 2
        for attempt in range(max_retries):
            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents=user_prompt,
                    config=types.GenerateContentConfig(
                        system_instruction=SYSTEM_INSTRUCTIONS,
                        tools=tools_list,
                        temperature=0.2,
                    ),
                )
                if response and response.text:
                    return sanitize_output(response.text)
            except Exception as err:
                err_str = str(err)
                last_error = err_str
                # Agar 404 (model not found) hai toh foran agle model par chale jao
                if "404" in err_str or "NOT_FOUND" in err_str:
                    break
                # Agar rate limit ya server busy hai toh thoda wait kar ke retry karo
                if "503" in err_str or "429" in err_str or "RESOURCE_EXHAUSTED" in err_str:
                    if attempt < max_retries - 1:
                        time.sleep(2)
                        continue

    return f"- Server is experiencing high traffic or all models failed. Last error: {last_error}"