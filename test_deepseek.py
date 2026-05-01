import asyncio
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider

from pydantic_ai import Agent

async def main():
    provider = OpenAIProvider(
        base_url="https://api.deepseek.com",
        api_key="sk-44c79a5a04494c1788ccd723ac565166"
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
