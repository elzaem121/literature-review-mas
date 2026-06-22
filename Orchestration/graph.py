from langgraph.graph import StateGraph, END
from Orchestration.state import PipelineState

# Import ALL nodes
from Orchestration.nodes import (
    pre_search_node, search_node,
    pre_screening_node, screening_node,
    pre_extraction_node, extraction_node
)

workflow = StateGraph(PipelineState)

# 1. Add all nodes to the graph
workflow.add_node("pre_search", pre_search_node)
workflow.add_node("search_agent", search_node)

workflow.add_node("pre_screening", pre_screening_node)
workflow.add_node("screening_agent", screening_node)

workflow.add_node("pre_extraction", pre_extraction_node)
workflow.add_node("extraction_agent", extraction_node)

# 2. Wire them up in sequence (Status -> Work -> Status -> Work)
workflow.set_entry_point("pre_search")

workflow.add_edge("pre_search", "search_agent")
workflow.add_edge("search_agent", "pre_screening")

workflow.add_edge("pre_screening", "screening_agent")
workflow.add_edge("screening_agent", "pre_extraction")

workflow.add_edge("pre_extraction", "extraction_agent")
workflow.add_edge("extraction_agent", END)

# 3. Compile
app = workflow.compile()