from pydantic import BaseModel, Field
from typing import List, Optional, Literal

class Node(BaseModel):
    id: str = Field(description="Unique normalized ID (no spaces), e.g., 'lead', 'category_1', 'pcb_capacitors'")
    label: str = Field(description="Display name, e.g., 'Lead', 'Category 1'")
    node_type: Literal[
        "Material", 
        "Component", 
        "ProductCategory", 
        "Jurisdiction", 
        "Action", 
        "Clause"
    ]

class TemporalCondition(BaseModel):
    effective_to: Optional[str] = Field(None, description="Strict ISO date if available, e.g., '2025-12-31'")
    expiry_condition: Optional[str] = Field(None, description="Text condition, e.g., 'Expires on various phased dates'")

class Edge(BaseModel):
    source_node_id: str
    target_node_id: str
    relationship: Literal[
        "RESTRICTED_IN", 
        "EXEMPT_FOR", 
        "MUST_BE_REMOVED_FROM", 
        "INCLUDES", 
        "REQUIRES_SPECIAL_TREATMENT",
        "CONDITIONAL_ON"
    ]
    threshold: Optional[str] = Field(None, description="e.g., '< 30 W' or '5 mg per burner'")
    temporal_validity: Optional[TemporalCondition] = None
    source_reference: str = Field(description="The exact legal pointer, e.g., 'WEEE Annex VII.1' or 'RoHS Annex III'")

class KnowledgeGraphExtraction(BaseModel):
    nodes: List[Node]
    edges: List[Edge]