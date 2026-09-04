import streamlit as st
import sys
import os

# Root project folder ko path mein add karna taake 'backend' package theek se import ho
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend.agent import ask_ai
from backend.database import get_all_opportunities
from backend.web_search import search_web as search_scholarships_web

st.set_page_config(page_title="ScholarAI - Smart Opportunity Advisor", layout="wide", page_icon="🎓")

# ---------------- Custom CSS Styling ----------------
st.markdown("""
<style>
    /* Overall app background */
    .stApp {
        background: linear-gradient(180deg, #0f1117 0%, #151823 100%);
    }

    /* Main title */
    h1 {
        color: #ffffff !important;
        font-weight: 800 !important;
        padding-bottom: 0px;
    }

    /* Subheaders */
    h2, h3 {
        color: #e8e8e8 !important;
        font-weight: 600 !important;
    }

    /* Sidebar */
    section[data-testid="stSidebar"] {
        background-color: #11141c;
        border-right: 1px solid #2a2f3d;
    }
    section[data-testid="stSidebar"] h1, 
    section[data-testid="stSidebar"] h2, 
    section[data-testid="stSidebar"] h3 {
        color: #ffffff !important;
    }

    /* Tabs */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
        background-color: #11141c;
        padding: 6px;
        border-radius: 12px;
    }
    .stTabs [data-baseweb="tab"] {
        height: 45px;
        border-radius: 8px;
        color: #b0b0b0;
        font-weight: 600;
        padding: 0px 18px;
    }
    .stTabs [aria-selected="true"] {
        background-color: #6c5ce7 !important;
        color: #ffffff !important;
    }

    /* Buttons */
    .stButton > button {
        background: linear-gradient(90deg, #6c5ce7, #8e6cf0);
        color: white;
        border: none;
        border-radius: 10px;
        padding: 10px 22px;
        font-weight: 600;
        transition: all 0.2s ease-in-out;
    }
    .stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 14px rgba(108, 92, 231, 0.4);
    }

    /* Text areas / text inputs / number input */
    .stTextArea textarea, .stTextInput input, .stNumberInput input {
        background-color: #1a1e29 !important;
        color: #ffffff !important;
        border: 1px solid #2a2f3d !important;
        border-radius: 8px !important;
    }

    /* Answer / result cards */
    div[data-testid="stMarkdownContainer"] ul {
        background-color: #1a1e29;
        padding: 16px 20px;
        border-radius: 12px;
        border: 1px solid #2a2f3d;
    }

    /* Info & error boxes */
    .stAlert {
        border-radius: 10px;
    }

    /* Spinner text */
    .stSpinner > div {
        color: #6c5ce7 !important;
    }
</style>
""", unsafe_allow_html=True)
# ------------------------------------------------------

st.title("🎓 ScholarAI Assistant")
st.caption("Smart Scholarship & Opportunity Advisor — powered by AI")

st.sidebar.header("📋 Student Profile")
degree = st.sidebar.text_input("Degree Program", value="BSCS")
cgpa = st.sidebar.number_input("Current CGPA", min_value=0.0, max_value=4.0, value=3.4, step=0.01)
location = st.sidebar.text_input("Location / Country", value="Pakistan")

student_payload = {
    "degree": degree,
    "cgpa": cgpa,
    "location": location
}

tab1, tab2, tab3 = st.tabs(["💬 AI Advisor", "🔍 Browse DB Opportunities", "🌐 Web Search"])

with tab1:
    st.subheader("Ask ScholarAI")
    user_query = st.text_area("Enter your query or request:", value="Find relevant scholarships for my profile and check eligibility.")
    if st.button("Submit Query"):
        with st.spinner("ScholarAI is processing tools and checking sources..."):
            try:
                response_text = ask_ai(user_query, student_payload)
                st.markdown("### Answer")
                st.markdown(response_text)
            except Exception as e:
                st.error(f"Error processing AI query: {str(e)}")

with tab2:
    st.subheader("Database Opportunities")
    if st.button("Load DB Records"):
        try:
            records = get_all_opportunities()
            if isinstance(records, list) and records:
                for item in records:
                    title = item.get("title", "Opportunity")
                    opp_id = item.get("id", "")
                    desc = item.get("description", "")
                    st.markdown(f"- **{title}** (ID: `{opp_id}`)\n  {desc}")
            else:
                st.info("No records found.")
        except Exception as e:
            st.error(f"Error fetching DB records: {str(e)}")

with tab3:
    st.subheader("Live Web Search")
    search_q = st.text_input("Search Keyword", value="HEC Pakistan scholarships 2026")
    if st.button("Execute Web Search"):
        with st.spinner("Searching web sources..."):
            try:
                search_results = search_scholarships_web(search_q)
                if isinstance(search_results, list) and search_results:
                    # Markdown Table Construction
                    table_markdown = "| Scholarship Name | Deadline | Amount | Details / Criteria | Official Link |\n"
                    table_markdown += "| :--- | :--- | :--- | :--- | :--- |\n"
                    
                    for item in search_results:
                        title = item.get("title", "Result")
                        url = item.get("url", "#")
                        deadline = item.get("deadline", "Not Specified")
                        amount = item.get("amount", "Varies")
                        criteria = item.get("criteria", item.get("content", ""))[:120].replace("\n", " ")
                        
                        if url:
                            table_markdown += f"| **{title}** | {deadline} | {amount} | {criteria}... | [Open Link]({url}) |\n"
                        else:
                            table_markdown += f"| **{title}** | {deadline} | {amount} | {criteria}... | N/A |\n"
                            
                    st.markdown(table_markdown)
                else:
                    st.info("No search results found.")
            except Exception as e:
                st.error(f"Error executing web search: {str(e)}")