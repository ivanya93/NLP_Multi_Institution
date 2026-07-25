import anthropic
import os
import json
import pandas as pd
from datetime import datetime

from dotenv import load_dotenv
load_dotenv()

client = anthropic.Anthropic()

# Load dataset
_base_path = os.path.dirname(os.path.abspath(__file__))
df = pd.read_csv(os.path.join(_base_path, "data", "final_merged_dataset_Food_Climate_Project.csv"))
print(f"✅ Dataset loaded: {len(df):,} rows, {len(df.columns)} columns")

# --- MEMORY: stores the full conversation ---
conversation_history = []
insights_log = []  # stores all insights for export

# --- TOOLS ---

def get_dataset_info() -> str:
    return json.dumps({
        "rows": len(df),
        "columns": list(df.columns),
        "years": f"{int(df['year'].min())} to {int(df['year'].max())}",
        "countries": int(df['country'].nunique()),
        "food_items": int(df['food_item'].nunique()),
        "sample_foods": df['food_item'].unique()[:5].tolist()
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
                "avg_ghg_kg": round(float(country_df['GHG_kg'].mean()), 4)
            }
    return json.dumps(results, indent=2)

# --- TOOL DEFINITIONS ---

tools = [
    {
        "name": "get_dataset_info",
        "description": "Get an overview of the dataset structure, columns, and coverage",
        "input_schema": {"type": "object", "properties": {}}
    },
    {
        "name": "query_data",
        "description": "Query the dataset to answer questions about emissions, production, temperature change, or GHG",
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
        "description": "Get detailed food production and climate data for a specific country",
        "input_schema": {
            "type": "object",
            "properties": {
                "country": {"type": "string", "description": "Country name"}
            },
            "required": ["country"]
        }
    },
    {
        "name": "compare_countries",
        "description": "Compare food production, emissions and climate data across multiple countries",
        "input_schema": {
            "type": "object",
            "properties": {
                "countries": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of country names to compare"
                }
            },
            "required": ["countries"]
        }
    }
]

system = """You are an expert data analyst specializing in food systems and climate change.
You have access to a dataset with 101,597 records covering food production, CO2 emissions,
greenhouse gas (GHG) emissions per kg of food, and temperature change across countries from 1961 onwards.

IMPORTANT: You have full memory of this conversation. Use previous questions and answers
to give better, connected insights. If the user says "that country", "those items", or 
"tell me more", refer back to what was discussed earlier.

Always use your tools to fetch real data. Give specific numbers and actionable insights."""

# --- AGENT LOOP WITH MEMORY ---

def run_agent(user_message: str):
    print(f"\n👤 You: {user_message}")
    print("-" * 50)

    # Add user message to memory
    conversation_history.append({
        "role": "user",
        "content": user_message
    })

    while True:
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1024,
            system=system,
            tools=tools,
            messages=conversation_history  # full history every time
        )

        if response.stop_reason == "tool_use":
            tool_results = []
            for tool_use in (b for b in response.content if b.type == "tool_use"):
                tool_name = tool_use.name
                tool_input = tool_use.input

                print(f"🔧 Using tool: {tool_name}")

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

            # Add tool interaction to memory
            conversation_history.append({"role": "assistant", "content": response.content})
            conversation_history.append({"role": "user", "content": tool_results})

        else:
            final_answer = response.content[0].text
            print(f"\n🤖 Agent: {final_answer}\n")

            # Save to memory and insights log
            conversation_history.append({
                "role": "assistant",
                "content": final_answer
            })
            insights_log.append({
                "question": user_message,
                "answer": final_answer,
                "timestamp": datetime.now().strftime("%H:%M:%S")
            })
            break

# --- EXPORT INSIGHTS TO FILE ---

def save_insights():
    if not insights_log:
        print("⚠️  No insights to save yet.")
        return

    filename = f"insights_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    filepath = os.path.join(_base_path, "insights", filename)

    with open(filepath, "w") as f:
        f.write("=" * 60 + "\n")
        f.write("AI DATA ANALYST AGENT — SESSION INSIGHTS\n")
        f.write(f"Dataset: Food & Climate Project\n")
        f.write(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
        f.write("=" * 60 + "\n\n")

        for i, item in enumerate(insights_log, 1):
            f.write(f"[{item['timestamp']}] Q{i}: {item['question']}\n")
            f.write("-" * 40 + "\n")
            f.write(f"{item['answer']}\n\n")

    print(f"✅ Insights saved to: {filename}")

# --- INTERACTIVE CHAT LOOP ---

print("\n🌍 Food & Climate Data Analyst Agent — with Memory")
print("Commands: type your question | 'save' = export insights | 'history' = show conversation | 'exit' = quit")
print("-" * 60)

while True:
    user_input = input("\n👤 You: ").strip()

    if not user_input:
        continue

    if user_input.lower() in ["exit", "quit", "q"]:
        print("👋 Goodbye! Great analysis session.")
        break

    elif user_input.lower() == "save":
        save_insights()

    elif user_input.lower() == "history":
        print(f"\n📚 Conversation so far: {len(insights_log)} exchanges")
        for i, item in enumerate(insights_log, 1):
            print(f"  Q{i}: {item['question'][:60]}...")

    else:
        run_agent(user_input)
