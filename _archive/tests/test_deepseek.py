import asyncio
import os
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider

from pydantic_ai import Agent

async def main():
    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        raise RuntimeError("DEEPSEEK_API_KEY is required after rotating the exposed key.")

    provider = OpenAIProvider(
        base_url="https://api.deepseek.com",
        api_key=api_key,
    )
    model = OpenAIChatModel("deepseek-v4-pro", provider=provider)
    agent = Agent(model)
    
    print("Testing DeepSeek V4 Pro connection via Agent...")
    try:
        result = await agent.run("Say hello!")
        print("Success!")
        print(f"Response: {result.data}")
    except Exception as e:
        print(f"DeepSeek Failed: {e}")

if __name__ == "__main__":
    asyncio.run(main())
