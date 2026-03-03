from pydantic import BaseModel, Field
from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIChatModel, OpenAIModelName
from pydantic_ai.providers.openai import OpenAIProvider
from app.core.config import settings
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SUMMARY_PROMPT_PATH = os.path.join(BASE_DIR, "../prompts/draft_summary.md")
ANALYSIS_PROMPT_PATH = os.path.join(BASE_DIR, "../prompts/sentiment_analysis.md")

def load_prompt(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()

# Load prompts from files
summary_instructions = load_prompt(SUMMARY_PROMPT_PATH)
analysis_instructions = load_prompt(ANALYSIS_PROMPT_PATH)

# Model names
SUMMARY_MODEL_NAME: OpenAIModelName = "gpt-4.1"
ANALYSIS_MODEL_NAME: OpenAIModelName = "gpt-5-nano"

# Provider
openai_provider = OpenAIProvider(api_key=settings.OPENAI_API_KEY)

# Models
summary_model = OpenAIChatModel(
    SUMMARY_MODEL_NAME,
    provider=openai_provider,
)

analysis_model = OpenAIChatModel(
    model_name=ANALYSIS_MODEL_NAME,
    provider=openai_provider
)

# Output schema for analysis agent
class Sentiment(BaseModel):
    sentiment_analysis: str = Field(description="Given a comment you are to classify it as: [positive, neutral, negative]")
    sentiment_score: str = Field(description="Given a comment you are to assign it a numeric value scaling positive to 1 and negative to 0")
    sentiment_keywords: str = Field(description="Given a comment you are to analyse and list out keywords which heavily impact the sentiment of the sentence")

# Agents
summary_agent = Agent(
    summary_model,
    instructions=summary_instructions
)

analysis_agent = Agent(
    analysis_model,
    instructions=analysis_instructions,
    output_type=Sentiment
)
