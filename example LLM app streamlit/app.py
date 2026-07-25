import streamlit as st
import anthropic
import os
import json
import pandas as pd
from datetime import datetime

# --- PAGE CONFIG ---
st.set_page_config(
    page_title="Food & Climate Data Agent",
    page_icon="🌍",
    layout="wide"
)

# --- API KEY ---
os.environ["ANTHROPIC_API_KEY"] = st.secrets["ANTHROPIC_API_KEY"]
client = anthropic.Anthropic()

# --- LOAD DATA ---
@st.cache_data
def load_data():
    import os
    base_path = os.path.dirname(os.path.abspath(__file__))
    return pd.read_csv(os.path.join(base_path, "data", "final_merged_dataset_Food_Climate_Project.csv"))

df = load_data()

# --- TOOLS ---
def get_dataset_info() -> str:
    return json.dumps({
        "rows": len(df),
        "columns": list(df.columns),
        "years": f"{int(df['year'].min())} to {int(df['year'].max())}",
        "countries": int(df['country'].nunique()),
        "food_items": int(df['food_item'].nunique()),
    }, indent=2)

def query_data(question: str) -> str:
    try:
        q = question.lower()
        if "emission" in q or "co2" in q:
            result = df.groupby("food_item")["emissions_CO2eq_AR5"].mean().sort_values(ascending=False).head(10)
            return result.round(2).to_json()
        elif "production" in q and "country" in q:
            result = df.groupby("country")["production_tonnes"].sum().sort_values(ascending=False).head(10)
            return result.round(2).to_json()
        elif "temp" in q:
            result = df.groupby("year")["avg_year_temp_change"].mean()
            return result.round(4).to_json()
        elif "ghg" in q or "greenhouse" in q:
            result = df.groupby("food_item")["GHG_kg"].mean().sort_values(ascending=False).head(10)
            return result.round(4).to_json()
        elif "trend" in q or "year" in q:
            result = df.groupby("year")["production_tonnes"].sum()
            return result.round(2).to_json()
        else:
            return df.describe().round(2).to_json()
    except Exception as e:
        return f"Error: {e}"

def get_country_data(country: str) -> str:
    country_df = df[df['country'].str.lower() == country.lower()]
    if country_df.empty:
        country_df = df[df['country'].str.lower().str.contains(country.lower())]
    if country_df.empty:
        return f"No data found for: {country}"
    return json.dumps({
        "country": country_df['country'].iloc[0],
        "years": f"{int(country_df['year'].min())} to {int(country_df['year'].max())}",
        "total_production_tonnes": round(float(country_df['production_tonnes'].sum()), 2),
        "avg_temp_change": round(float(country_df['avg_year_temp_change'].mean()), 4),
        "avg_emissions_CO2": round(float(country_df['emissions_CO2eq_AR5'].mean()), 2),
        "top_foods": country_df.groupby('food_item')['production_tonnes'].sum().sort_values(ascending=False).head(5).round(2).to_dict()
    }, indent=2)

def compare_countries(countries: list) -> str:
    results = {}
    for country in countries:
        country_df = df[df['country'].str.lower() == country.lower()]
        if not country_df.empty:
            results[country] = {
                "total_production": round(float(country_df['production_tonnes'].sum()), 2),
                "avg_emissions": round(float(country_df['emissions_CO2eq_AR5'].mean()), 2),
                "avg_temp_change": round(float(country_df['avg_year_temp_change'].mean()), 4),
            }
    return json.dumps(results, indent=2)

tools = [
    {
        "name": "get_dataset_info",
        "description": "Get an overview of the dataset structure and coverage",
        "input_schema": {"type": "object", "properties": {}}
    },
    {
        "name": "query_data",
        "description": "Query the dataset to answer questions about emissions, production, temperature, or GHG",
        "input_schema": {
            "type": "object",
            "properties": {
                "question": {"type": "string", "description": "The analytical question to answer"}
            },
            "required": ["question"]
        }
    },
    {
        "name": "get_country_data",
        "description": "Get detailed data for a specific country",
        "input_schema": {
            "type": "object",
            "properties": {
                "country": {"type": "string"}
            },
            "required": ["country"]
        }
    },
    {
        "name": "compare_countries",
        "description": "Compare multiple countries on production, emissions and climate",
        "input_schema": {
            "type": "object",
            "properties": {
                "countries": {"type": "array", "items": {"type": "string"}}
            },
            "required": ["countries"]
        }
    }
]

system = """You are an expert data analyst specializing in food systems and climate change.
You have access to a dataset with 101,597 records covering food production, CO2 emissions,
greenhouse gas emissions, and temperature change across countries from 1961 onwards.
You have full memory of this conversation — use previous context to give connected insights.
Always use your tools to fetch real data. Be specific with numbers."""

# --- AGENT FUNCTION ---
def run_agent(user_message: str, history: list) -> str:
    messages = history + [{"role": "user", "content": user_message}]

    while True:
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1024,
            system=system,
            tools=tools,
            messages=messages
        )

        if response.stop_reason == "tool_use":
            tool_results = []
            for tool_use in (b for b in response.content if b.type == "tool_use"):
                tool_name = tool_use.name
                tool_input = tool_use.input

                if tool_name == "get_dataset_info":
                    result = get_dataset_info()
                elif tool_name == "query_data":
                    result = query_data(tool_input["question"])
                elif tool_name == "get_country_data":
                    result = get_country_data(tool_input["country"])
                elif tool_name == "compare_countries":
                    result = compare_countries(tool_input["countries"])
                else:
                    result = "Tool not found"

                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tool_use.id,
                    "content": result
                })

            messages.append({"role": "assistant", "content": response.content})
            messages.append({"role": "user", "content": tool_results})
        else:
            return response.content[0].text

# --- SESSION STATE ---
if "messages" not in st.session_state:
    st.session_state.messages = []
if "history" not in st.session_state:
    st.session_state.history = []

# --- SIDEBAR ---
with st.sidebar:
    st.title("🌍 Data Agent")
    st.markdown("---")

    st.subheader("📁 Project")
    st.success("Food & Climate")
    st.info(f"**{len(df):,} rows** · {len(df.columns)} columns")
    st.info(f"**Years:** {int(df['year'].min())} – {int(df['year'].max())}")
    st.info(f"**Countries:** {df['country'].nunique()}")

    st.markdown("---")
    st.subheader("💬 Session")
    st.metric("Questions asked", len(st.session_state.messages) // 2)

    st.markdown("---")

    # Save insights button
    if st.button("💾 Save insights", use_container_width=True):
        if st.session_state.messages:
            filename = f"insights_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
            base_path = os.path.dirname(os.path.abspath(__file__))
            filepath = os.path.join(base_path, "insights", filename)
            with open(filepath, "w") as f:
                f.write("FOOD & CLIMATE AGENT — SESSION INSIGHTS\n")
                f.write(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
                f.write("=" * 50 + "\n\n")
                for msg in st.session_state.messages:
                    role = "You" if msg["role"] == "user" else "Agent"
                    f.write(f"{role}: {msg['content']}\n\n")
            st.success(f"Saved: {filename}")
        else:
            st.warning("No conversation to save yet.")

    # Clear chat button
    if st.button("🗑️ Clear chat", use_container_width=True):
        st.session_state.messages = []
        st.session_state.history = []
        st.rerun()

    st.markdown("---")
    st.caption("Built with Claude + Streamlit")

# --- MAIN AREA ---
st.title("🌍 Food & Climate Data Analyst")
st.caption("Ask me anything about food production, CO2 emissions, and climate change across countries.")

# Suggested questions
st.markdown("**Try asking:**")
cols = st.columns(3)
suggestions = [
    "Which food has highest CO2 emissions?",
    "Show me data for Brazil",
    "Compare Portugal and Spain"
]
for i, suggestion in enumerate(suggestions):
    if cols[i].button(suggestion, use_container_width=True):
        st.session_state.pending = suggestion

st.markdown("---")

# Display chat history
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# Handle suggestion buttons
if "pending" in st.session_state:
    prompt = st.session_state.pop("pending")
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)
    with st.chat_message("assistant"):
        with st.spinner("Analyzing..."):
            response = run_agent(prompt, st.session_state.history)
        st.markdown(response)
    st.session_state.messages.append({"role": "assistant", "content": response})
    st.session_state.history.append({"role": "user", "content": prompt})
    st.session_state.history.append({"role": "assistant", "content": response})
    st.rerun()

# Chat input
if prompt := st.chat_input("Ask a question about the data..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)
    with st.chat_message("assistant"):
        with st.spinner("Analyzing..."):
            response = run_agent(prompt, st.session_state.history)
        st.markdown(response)
    st.session_state.messages.append({"role": "assistant", "content": response})
    st.session_state.history.append({"role": "user", "content": prompt})
    st.session_state.history.append({"role": "assistant", "content": response})
    st.rerun()