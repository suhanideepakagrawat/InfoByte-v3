from pydantic import BaseModel, Field

class InfoByteSynthesis(BaseModel):
    factual_summary: str = Field(
        description="A rigorous synthesis of the provided source blocks. Must ONLY pull from the text blocks. Zero external injection allowed."
    )
    llm_overview: str = Field(
        description="Your own expert engineering overview, concepts breakdown, and independent architectural advice regarding the user query topic."
    )