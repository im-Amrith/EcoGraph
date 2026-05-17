import os
import json
import requests
from dotenv import load_dotenv
from groq import Groq
import instructor
from pydantic import BaseModel, Field

load_dotenv()

# ==========================================
# 1. CREDENTIALS & SETUP
# ==========================================
TG_HOST = "https://tg-a13de013-6c5d-4123-958a-fcec883464a9.tg-2635877100.i.tgcloud.io" # NO trailing slash
TG_GRAPH = "EcoGraph"
TG_SECRET = "36se9igvh1iv09f3ptn269akitaifkr6"

# Initialize Groq with Instructor for strict JSON extraction
groq_client = Groq()
instructor_client = instructor.from_groq(groq_client, mode=instructor.Mode.JSON)

class EntityExtraction(BaseModel):
    entity_id: str = Field(description="The normalized ID of the entity, e.g., 'lead', 'CEEW1', 'ministry'")
    entity_type: str = Field(description="Must be one of: Material, Component, ProductCategory, Jurisdiction, ActionNode, Clause")

# ==========================================
# 2. TIGERGRAPH AUTHENTICATION
# ==========================================
def get_tg_token():
    """Automatically exchanges your Secret for a temporary REST API Token."""
    clean_host = TG_HOST.rstrip('/')
    url = f"{clean_host}/gsql/v1/tokens"
    
    response = requests.post(url, json={"secret": TG_SECRET})
    if response.status_code == 200 and not response.json().get("error"):
        return response.json()["token"]
    print(f"❌ Auth Failed: {response.text}")
    return None

# ==========================================
# 3. GRAPHRAG PIPELINE
# ==========================================
def extract_entity_from_question(question: str) -> EntityExtraction:
    """Uses Groq to figure out exactly what node the user is asking about."""
    return instructor_client.chat.completions.create(
        model="llama-3.1-8b-instant",
        response_model=EntityExtraction,
        messages=[
            {"role": "system", "content": "You are a graph routing agent. Extract the primary entity from the user's question and classify its type."},
            {"role": "user", "content": question}
        ]
    )

def fetch_graph_neighborhood(token: str, entity_type: str, entity_id: str) -> str:
    """Hits the TigerGraph REST API to get all connected edges for this node."""
    clean_host = TG_HOST.rstrip('/')
    # TigerGraph built-in endpoint for edge traversal
    url = f"{clean_host}/restpp/graph/{TG_GRAPH}/edges/{entity_type}/{entity_id}"
    
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(url, headers=headers)
    
    if response.status_code != 200 or response.json().get("error"):
        return "No graph data found for this entity."

    edges = response.json().get("results", [])
    if not edges:
        return "Entity exists, but has no connections in the graph."

    # Convert the raw JSON graph response into readable text context for the LLM
    context_lines = [f"Graph Context for {entity_id}:"]
    for edge in edges:
        target_type = edge.get("target_type")
        target_id = edge.get("directed_to_id")
        rel = edge.get("e_type")
        attrs = edge.get("attributes", {})
        
        # Build a readable sentence from the graph edge
        sentence = f"- {entity_id} ({entity_type}) is {rel} {target_id} ({target_type})."
        
        # Add conditions if they exist
        if attrs.get("threshold"): sentence += f" Threshold: {attrs['threshold']}."
        if attrs.get("effective_to"): sentence += f" Effective until: {attrs['effective_to']}."
        if attrs.get("source_ref"): sentence += f" Source: {attrs['source_ref']}."
        
        context_lines.append(sentence)

    return "\n".join(context_lines)

def generate_final_answer(question: str, graph_context: str) -> str:
    """Feeds the graph data back to Groq to answer the question."""
    prompt = f"""
    You are an expert Environmental Policy AI. Answer the user's question strictly using the provided Graph Context.
    Do not hallucinate outside information. If the answer is not in the context, state that clearly.
    
    GRAPH CONTEXT:
    {graph_context}
    
    USER QUESTION:
    {question}
    """
    
    response = groq_client.chat.completions.create(
        model="llama-3.1-8b-instant", # Use a currently supported model
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2
    )
    return response.choices[0].message.content

# ==========================================
# 4. EXECUTION
# ==========================================
if __name__ == "__main__":
    print("\n🌿 EcoGraph GraphRAG Terminal 🌿")
    print("Type 'exit' to quit.\n")
    
    token = get_tg_token()
    if not token:
        exit()

    while True:
        user_question = input("Ask the Graph: ")
        if user_question.lower() in ['exit', 'quit']:
            break
            
        print("\n[1/3] Routing question to target node...")
        try:
            target = extract_entity_from_question(user_question)
            print(f"      -> Found target: {target.entity_id} ({target.entity_type})")
        except Exception as e:
            print("      -> Could not identify an entity. Try rephrasing.")
            continue

        print("[2/3] Traversing TigerGraph...")
        context = fetch_graph_neighborhood(token, target.entity_type, target.entity_id)
        
        print("[3/3] Generating Answer...")
        answer = generate_final_answer(user_question, context)
        
        print("\n========================================")
        print("💡 ANSWER:")
        print(answer)
        print("========================================\n")
