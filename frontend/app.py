import streamlit as st
import sys
import os

# Backend folder ko path mein add karna taake functions direct import ho sakein
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../backend')))

from agent import run_agent  # Aap ke agent function ka main handler
from database import get_all_opportunities  # DB records ke liye
from web_search import search_scholarships_web  # Web search ke liye

st.set_page_config(page_title="ScholarAI - Smart Opportunity Advisor", layout="wide")
st.title("🎓 ScholarAI Assistant")

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
                # Direct agent function call (No HTTP requests needed)
                response_text = run_agent(user_query, student_payload)
                st.markdown("### Answer")
                st.write(response_text)
            except Exception as e:
                st.error(f"Error processing AI query: {str(e)}")

with tab2:
    st.subheader("Database Opportunities")
    if st.button("Load DB Records"):
        try:
            records = get_all_opportunities()
            st.json(records)
        except Exception as e:
            st.error(f"Error fetching DB records: {str(e)}")

with tab3:
    st.subheader("Live Web Search")
    search_q = st.text_input("Search Keyword", value="HEC Pakistan scholarships 2026")
    if st.button("Execute Web Search"):
        try:
            search_results = search_scholarships_web(search_q)
            st.write(search_results)
        except Exception as e:
            st.error(f"Error executing web search: {str(e)}")