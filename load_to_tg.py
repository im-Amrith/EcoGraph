import json
import requests
import os

# ==========================================
# 1. TIGERGRAPH CREDENTIALS
# ==========================================
TG_HOST = "https://tg-a13de013-6c5d-4123-958a-fcec883464a9.tg-2635877100.i.tgcloud.io"
TG_GRAPH = "EcoGraph"
TG_SECRET = "36se9igvh1iv09f3ptn269akitaifkr6" 

CHECKPOINT_FILE = "eco_graph_checkpoint.jsonl"

def get_tg_token():
    """Automatically exchanges your Secret for a temporary REST API Token using a GET request."""
    print("Authenticating with TigerGraph...")
    
    # Strip any accidental trailing slashes from the URL
    clean_host = TG_HOST.rstrip('/')
    
    # Use the gsql v1 tokens endpoint
    url = f"{clean_host}/gsql/v1/tokens"
    
    response = requests.post(url, json={"secret": TG_SECRET})
    
    if response.status_code == 200:
        res_json = response.json()
        if not res_json.get("error"):
            print("✅ Authentication successful!")
            return res_json["token"]
        else:
            print(f"❌ TigerGraph Error: {res_json.get('message')}")
            return None
    else:
        print(f"❌ Auth Failed: HTTP {response.status_code}")
        print(response.text)
        return None
    
def load_and_deduplicate():
    print("Reading extracted data...")
    raw_nodes = {}
    raw_edges = set() 
    edges_list = []
    
    if not os.path.exists(CHECKPOINT_FILE):
        print(f"Error: {CHECKPOINT_FILE} not found!")
        return {}, []

    with open(CHECKPOINT_FILE, 'r', encoding='utf-8') as f:
        for line in f:
            if not line.strip(): continue
            data = json.loads(line)
            
            for node in data.get("nodes", []):
                raw_nodes[node["id"]] = node 
                
            for edge in data.get("edges", []):
                edge_fingerprint = f"{edge['source_node_id']}-{edge['relationship']}-{edge['target_node_id']}"
                if edge_fingerprint not in raw_edges:
                    raw_edges.add(edge_fingerprint)
                    edges_list.append(edge)
                    
    print(f"Unique Nodes found: {len(raw_nodes)}")
    print(f"Unique Edges found: {len(edges_list)}")
    return raw_nodes, edges_list

def push_to_tigergraph(token, nodes_dict, edges_list):
    print("\nFormatting payload for TigerGraph...")
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    tg_payload = {
        "vertices": {},
        "edges": {}
    }
    
    # Valid schemas according to TigerGraph
    valid_vertices = {"Material", "Component", "ProductCategory", "Jurisdiction", "ActionNode", "Clause"}
    valid_edges = {"INCLUDES", "RESTRICTED_IN", "REQUIRES", "EXEMPT_FOR", "MUST_BE_REMOVED_FROM", "REQUIRES_SPECIAL_TREATMENT", "CONDITIONAL_ON"}
    
    valid_edge_pairs = {
        "INCLUDES": {("ProductCategory", "ProductCategory"), ("Clause", "Clause"), ("Component", "Component")},
        "RESTRICTED_IN": {("ProductCategory", "Material"), ("Material", "ProductCategory"), ("Material", "Component")},
        "REQUIRES": {("Jurisdiction", "ActionNode"), ("ActionNode", "ActionNode"), ("Component", "ActionNode")},
        "EXEMPT_FOR": {("Material", "ProductCategory"), ("Material", "Component")},
        "MUST_BE_REMOVED_FROM": {("Material", "ProductCategory"), ("Component", "ProductCategory")},
        "REQUIRES_SPECIAL_TREATMENT": {("ProductCategory", "ActionNode"), ("Component", "Material")},
        "CONDITIONAL_ON": {("ActionNode", "Material"), ("ActionNode", "Clause"), ("ProductCategory", "Clause")}
    }
    
    # 1. Format Nodes
    for n_id, node_data in nodes_dict.items():
        n_type = node_data["node_type"]
        if n_type not in valid_vertices:
            continue
            
        if n_type not in tg_payload["vertices"]:
            tg_payload["vertices"][n_type] = {}
            
        tg_payload["vertices"][n_type][n_id] = {
            "id": {"value": n_id},
            "label": {"value": node_data["label"]}
        }

    # 2. Format Edges
    for edge in edges_list:
        rel = edge["relationship"]
        if rel not in valid_edges:
            continue
            
        s_id = edge["source_node_id"]
        t_id = edge["target_node_id"]
        
        s_node = nodes_dict.get(s_id)
        t_node = nodes_dict.get(t_id)
        
        if not s_node or not t_node: continue
            
        s_type = s_node["node_type"]
        t_type = t_node["node_type"]
        
        if s_type not in valid_vertices or t_type not in valid_vertices:
            continue
            
        # Check against schema constraints for edge pairs
        if (s_type, t_type) not in valid_edge_pairs.get(rel, set()):
            continue
        
        threshold = edge.get("threshold") or ""
        source_ref = edge.get("source_reference") or ""
        
        effective_to = ""
        expiry_cond = ""
        if edge.get("temporal_validity"):
            effective_to = edge["temporal_validity"].get("effective_to") or ""
            expiry_cond = edge["temporal_validity"].get("expiry_condition") or ""

        if s_type not in tg_payload["edges"]: tg_payload["edges"][s_type] = {}
        if s_id not in tg_payload["edges"][s_type]: tg_payload["edges"][s_type][s_id] = {}
        if rel not in tg_payload["edges"][s_type][s_id]: tg_payload["edges"][s_type][s_id][rel] = {}
        if t_type not in tg_payload["edges"][s_type][s_id][rel]: tg_payload["edges"][s_type][s_id][rel][t_type] = {}
        
        tg_payload["edges"][s_type][s_id][rel][t_type][t_id] = {
            "threshold": {"value": str(threshold)},
            "effective_to": {"value": str(effective_to)},
            "expiry_condition": {"value": str(expiry_cond)},
            "source_ref": {"value": str(source_ref)}
        }

    print("Firing payload to TigerGraph Cloud...")
    url = f"{TG_HOST}/restpp/graph/{TG_GRAPH}"
    response = requests.post(url, headers=headers, json=tg_payload)
    
    if response.status_code == 200:
        res_data = response.json()
        if res_data.get("error"):
            print(f"❌ TG Execution Error: {res_data.get('message')}")
        else:
            print("\n✅ INGESTION SUCCESSFUL!")
            results = res_data.get('results', [{}])[0]
            print(f"Vertices inserted: {results.get('accepted_vertices', 0)}")
            print(f"Edges inserted: {results.get('accepted_edges', 0)}")
    else:
        print(f"❌ ERROR {response.status_code}: {response.text}")

if __name__ == "__main__":
    token = get_tg_token()
    if token:
        nodes, edges = load_and_deduplicate()
        if nodes and edges:
            push_to_tigergraph(token, nodes, edges)