import asyncio
import json
import os
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai import Agent
from engine.deps import create_deps
from strategy_families.base import StrategyProposal

async def main():
    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        raise RuntimeError("DEEPSEEK_API_KEY is required after rotating the exposed key.")

    # Setup Primary
    deepseek_provider = OpenAIProvider(
        base_url="https://api.deepseek.com", 
        api_key=api_key,
    )
    primary_model = OpenAIChatModel("deepseek-v4-flash", provider=deepseek_provider)

    # Setup Agent
    dev_agent = Agent(
        primary_model,
        output_type=StrategyProposal,
        system_prompt="Propose a BB strategy for BTC."
    )

    print("Testing DeepSeek V4 Pro with Swarm Agent Schema...")
    try:
        result = await dev_agent.run("Start optimization.")
        print("✅ Success!")
        print(f"Result: {result.data}")
    except Exception as e:
        print(f"❌ Failed: {e}")
        print(f"Type: {type(e)}")

if __name__ == "__main__":
    asyncio.run(main())
