from app.core.config import vision_model
from pydantic_ai import Agent, ImageUrl
from app.schemas.agent_output_schema import VisionOutput


class AgentService:

    def __init__(self):
        with open("app/prompts/prompt.md", "r", encoding="utf-8") as file:
            self.instructions = file.read()
        self.output_type = VisionOutput

        self.agent = Agent(model=vision_model,
                      instructions=self.instructions,
                      output_type=self.output_type,
                      retries=3
                    )
        
    async def run_agent(self, user_input: str, image_url: str):

        result = await self.agent.run(user_prompt=[user_input, ImageUrl(url=image_url)])
        output = result.output.model_dump()

        return output
    