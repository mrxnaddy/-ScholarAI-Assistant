import streamlit as st
import requests

API_BASE_URL = "http://127.0.0.1:8000"

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
                res = requests.post(
                    f"{API_BASE_URL}/ask-ai",
                    json={"message": user_query, "student": student_payload}
                )
                if res.status_code == 200:
                    st.markdown("### Answer")
                    st.write(res.json().get("answer"))
                else:
                    st.error(f"API Connection Failed (Status: {res.status_code})")
            except Exception as e:
                st.error(f"Could not connect to backend server: {str(e)}")

with tab2:
    st.subheader("Database Opportunities")
    if st.button("Load DB Records"):
        try:
            res = requests.get(f"{API_BASE_URL}/opportunities")
            if res.status_code == 200:
                st.json(res.json())
        except Exception as e:
            st.error(f"Error fetching DB records: {str(e)}")

with tab3:
    st.subheader("Live Web Search")
    search_q = st.text_input("Search Keyword", value="HEC Pakistan scholarships 2026")
    if st.button("Execute Web Search"):
        try:
            res = requests.get(f"{API_BASE_URL}/search-scholarships", params={"q": search_q})
            if res.status_code == 200:
                st.write(res.json())
        except Exception as e:
            st.error(f"Error executing web search: {str(e)}")