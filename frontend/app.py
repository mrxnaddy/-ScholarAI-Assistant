import streamlit as st
import sys
import os

# Root project folder ko path mein add karna taake 'backend' package theek se import ho
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend.agent import ask_ai
from backend.database import get_all_opportunities
from backend.web_search import search_web as search_scholarships_web

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
                    for item in search_results:
                        title = item.get("title", "Result")
                        url = item.get("url", "#")
                        content = item.get("content", "")
                        if url:
                            st.markdown(f"- **[{title}]({url})**\n  {content}")
                        else:
                            st.markdown(f"- **{title}**: {content}")
                else:
                    st.info("No search results found.")
            except Exception as e:
                st.error(f"Error executing web search: {str(e)}")