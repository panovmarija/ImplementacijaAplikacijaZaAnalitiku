#to_do
import streamlit as st
import requests
import pandas as pd
import json

BASE_URL = "http://127.0.0.1:8001"
FASTAPI_URL = "http://127.0.0.1:8001"

st.title("Cosmetic Recommendations")
user_query = st.text_area("Describe what you`re looking for:", placeholder="Hydrating primer", max_chars=200)

def to_md(data):
    md=""
    md+=f"{data["category"]} from {data["brand"]}\n"
    md+=f"\nPrice: {data["price"]}\n"
    md+=f"\nRating: {data["page_rating"]}\n"
    md+=f"\nDescription: {data["description"]}"
    return md

@st.cache_data(ttl=3600)
def get_catalog():
    response = requests.get(f"{FASTAPI_URL}/catalog")
    response.raise_for_status()
    return response.json()
try:
    api_data = get_catalog()
    selected_brand = st.sidebar.selectbox("Select a brand:", api_data.get("brands"), index=None)
    selected_category = st.sidebar.selectbox("Select a category:", api_data.get("categories"), index=None)
    selected_max_price=st.sidebar.slider("Maximum price:", 0, api_data.get("max_price"), api_data.get("max_price"),disabled=False)
except Exception as e:
    st.error(f"Failed to load or validate data: {e}")




if "api_data" not in st.session_state:
    st.session_state.api_data = None
def fetch_recommendations():
    with st.spinner("Loading results..."):
        try:
            response = requests.post(f"{FASTAPI_URL}/recommend", json={"query":user_query, "brand":selected_brand , "category":selected_category ,"max_price": selected_max_price})
            st.session_state.api_data = response.json()
        except Exception as e:
            st.session_state.api_data = {"error": str(e)}

with st.container( horizontal_alignment="center"):
    st.button("Get recommendations", on_click=fetch_recommendations)

if st.session_state.api_data:
    st.write("### Results:")
    for item in st.session_state.api_data:
        with st.expander(f"{item["rank"]}. {item["product_name"]}\n"  ):
            st.write(to_md(item))

elif not st.session_state.api_data:
    st.write("### No results")

 