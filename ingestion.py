import asyncio
import json
import os
import time
from typing import List, Literal, Optional
from pydantic import BaseModel, Field

from dotenv import load_dotenv
from groq import AsyncGroq
import instructor
from tenacity import retry, wait_exponential, stop_after_attempt

import fitz  # PyMuPDF
from langchain_text_splitters import RecursiveCharacterTextSplitter

load_dotenv()

# ==========================================
# 1. THE SCHEMA
# ==========================================

class Node(BaseModel):
    id: str = Field(description="Unique normalized ID (no spaces), e.g., 'lead', 'category_1'")
    label: str = Field(description="Display name, e.g., 'Lead', 'Category 1'")
    node_type: Literal[
        "Material", "Component", "ProductCategory", "Jurisdiction", "ActionNode", "Clause"
    ] = Field(description="The type of the node. MUST be exactly one of: 'Material', 'Component', 'ProductCategory', 'Jurisdiction', 'ActionNode', 'Clause'.")

class TemporalCondition(BaseModel):
    effective_to: Optional[str] = Field(None, description="Strict ISO date if available, e.g., '2025-12-31'")
    expiry_condition: Optional[str] = Field(None, description="Text condition, e.g., 'Expires on various phased dates'")

class Edge(BaseModel):
    source_node_id: str
    target_node_id: str
    relationship: Literal[
        "INCLUDES", "RESTRICTED_IN", "REQUIRES", "EXEMPT_FOR", "MUST_BE_REMOVED_FROM", "REQUIRES_SPECIAL_TREATMENT", "CONDITIONAL_ON"
    ] = Field(description="The relationship between nodes. MUST be exactly one of: 'INCLUDES', 'RESTRICTED_IN', 'REQUIRES', 'EXEMPT_FOR', 'MUST_BE_REMOVED_FROM', 'REQUIRES_SPECIAL_TREATMENT', 'CONDITIONAL_ON'.")
    threshold: Optional[str] = Field(None, description="e.g., '< 30 W'")
    temporal_validity: Optional[TemporalCondition] = None
    source_reference: str = Field(description="The exact legal pointer, e.g., 'WEEE Annex VII.1'")

class KnowledgeGraphExtraction(BaseModel):
    nodes: List[Node]
    edges: List[Edge]

# ==========================================
# 2. GROQ CLIENT SETUP
# ==========================================

client = instructor.from_groq(AsyncGroq(), mode=instructor.Mode.JSON)

CONCURRENCY_LIMIT = 1  
SEMAPHORE = asyncio.Semaphore(CONCURRENCY_LIMIT)
CHECKPOINT_FILE = "eco_graph_checkpoint.jsonl"
MAX_ERRORS = 10 
MODEL_NAME = "llama-3.1-8b-instant"

# ==========================================
# 3. THE ASYNC WORKER
# ==========================================

@retry(
    wait=wait_exponential(multiplier=2, min=10, max=120), 
    stop=stop_after_attempt(7),
    reraise=True
)
async def extract_triplets_from_chunk(chunk_id: int, text_chunk: str) -> Optional[KnowledgeGraphExtraction]:
    async with SEMAPHORE:
        print(f"[WORKER] Started processing chunk {chunk_id}...")
        try:
            extraction = await client.chat.completions.create(
                model=MODEL_NAME,
                temperature=0.0, 
                max_tokens=4000, # Increased to 4000 to allow complete JSONs
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are an expert environmental law parser. Extract entities and relationships. "
                            "CRITICAL INSTRUCTION: Do NOT extract exhaustive lists of every single product category. "
                            "Consolidate similar items. Limit your extraction to an absolute MAXIMUM of 5 nodes and 5 highly critical "
                            "relationships per chunk to ensure concise, accurate graph logic and strictly avoid token limits."
                        )
                    },
                    {
                        "role": "user",
                        "content": f"Extract knowledge from this legal text:\n\n{text_chunk}"
                    }
                ],
                response_model=KnowledgeGraphExtraction,
            )
            print(f"[WORKER] Successfully generated JSON for chunk {chunk_id}. Waiting 30s for rate limit...")
            await asyncio.sleep(30) 
            return extraction
        
        except Exception as e:
            err_msg = str(e).lower()
            if 'tokens per minute' in err_msg or 'rate limit' in err_msg or '429' in err_msg or '413' in err_msg:
                print(f"[WORKER] Rate limit / TPM exceeded for chunk {chunk_id}, waiting 60s before retry...")
                await asyncio.sleep(60)
            else:
                print(f"[ERROR] Failed on chunk {chunk_id}: {e}")
            raise e 

# ==========================================
# 4. ORCHESTRATOR & CHECKPOINTING 
# ==========================================

async def process_corpus(chunks_with_ids: List[tuple]):
    error_count = 0
    
    async def process_and_return(c_id, text):
        res = await extract_triplets_from_chunk(c_id, text)
        return c_id, res

    tasks = [process_and_return(c_id, text) for c_id, text in chunks_with_ids]

    with open(CHECKPOINT_FILE, "a", encoding="utf-8") as f:
        for future in asyncio.as_completed(tasks):
            if error_count >= MAX_ERRORS:
                print(f"[CIRCUIT BREAKER] Exceeded {MAX_ERRORS} errors. Halting.")
                break
                
            try:
                chunk_id, result = await future
                
                if result: 
                    checkpoint_data = {
                        "chunk_id": chunk_id,
                        "nodes": [node.model_dump() for node in result.nodes],
                        "edges": [edge.model_dump() for edge in result.edges]
                    }
                    f.write(json.dumps(checkpoint_data) + "\n")
                    f.flush() 
                    print(f"[WRITER] \u2705 Saved to disk: Chunk {chunk_id}")
                    
            except Exception as e:
                error_count += 1
                print(f"[FATAL ERROR] A chunk failed permanently. Total errors: {error_count}")

def get_completed_chunk_ids(filepath) -> set:
    completed = set()
    if not os.path.exists(filepath): 
        return completed
        
    with open(filepath, 'r', encoding='utf-8') as f:
        for line in f:
            if line.strip():
                try:
                    data = json.loads(line)
                    if "chunk_id" in data:
                        completed.add(data["chunk_id"])
                except: 
                    pass
    return completed

# ==========================================
# 5. EXECUTION ENTRY POINT
# ==========================================

def load_and_chunk_pdfs(directory_path: str) -> List[str]:
    print(f"Loading PDFs from {directory_path}...")
    full_text = ""
    for filename in os.listdir(directory_path):
        if filename.endswith(".pdf"):
            filepath = os.path.join(directory_path, filename)
            doc = fitz.open(filepath)
            for page in doc:
                full_text += page.get_text() + "\n"
            doc.close()
            print(f"Loaded: {filename}")
            
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=2000, 
        chunk_overlap=100,
        length_function=len,
    )
    return text_splitter.split_text(full_text)

if __name__ == "__main__":
    pdf_directory = "./data/raw" 
    
    if not os.path.exists(pdf_directory):
        print(f"Please create a folder named '{pdf_directory}' and add your PDFs.")
    else:
        all_chunks = load_and_chunk_pdfs(pdf_directory)
        completed_ids = get_completed_chunk_ids(CHECKPOINT_FILE)
        
        chunks_to_run = [
            (i, text) for i, text in enumerate(all_chunks) 
            if i not in completed_ids
        ]
            
        print(f"Total chunks: {len(all_chunks)} | Already completed: {len(completed_ids)}")
        print(f"Starting extraction pipeline for the missing {len(chunks_to_run)} chunks...")
        
        start_time = time.time()
        
        if len(chunks_to_run) > 0:
            asyncio.run(process_corpus(chunks_to_run))
        else:
            print("All chunks are already completed!")
            
        end_time = time.time()
        print(f"Pipeline finished in {round(end_time - start_time, 2)} seconds.")