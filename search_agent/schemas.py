from pydantic import BaseModel, Field
from typing import List

class AcademicQueryExpansionSchema(BaseModel):
    """
    Enforces a strict structured output schema from the LLM, ensuring
    perfect partition between the target semantic content and gatekeeping tokens.
    """
    synthetic_abstract: str = Field(
        description="A highly dense, jargon-rich academic paragraph (100-150 words) that represents the abstract of an ideal paper answering the query."
    )
    mandatory_entities: List[str] = Field(
        description="List of 3 to 5 VERY SHORT, exact technical terms or acronyms (e.g., 'MAS', 'scalability', 'robustness'). DO NOT use long phrases or sentences."
    )