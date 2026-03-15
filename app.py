import streamlit as st
import requests

st.title("AI Assistant")

user_input = st.text_input("Ask something")

if st.button("Submit"):
    response = requests.post(
        "NEMOTRON_API_URL",
        json={"prompt": user_input}
    )

    st.write(response.json()["answer"])