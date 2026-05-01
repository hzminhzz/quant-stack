import asyncio
from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider
import argparse

from pipeline_artifacts import DEFAULT_VALIDATION_ARTIFACT_PATH, load_validation_artifact
from strategy_families import get_strategy_family

# Setup the ChatMock Agent (gpt-5.4)
provider = OpenAIProvider(
    base_url='http://127.0.0.1:8000/v1',
    api_key='anything'
)

execution_model = OpenAIChatModel(
    'gpt-5.4',
    provider=provider
)

# Define the execution agent
execution_agent = Agent(
    execution_model,
    system_prompt=(
        "You are a quantitative developer writing a Freqtrade strategy. "
        "Return ONLY the Python code for a valid Freqtrade IStrategy class named 'PodcastAlphaStrategy'. "
        "Make sure to include necessary imports like 'from freqtrade.strategy import IStrategy'. "
        "Do not use markdown formatting like ```python or any explanations, just return the raw python code."
    )
)

def parse_args():
    parser = argparse.ArgumentParser(description="Phase 5: Freqtrade Execution Factory")
    parser.add_argument("--artifact-path", default=str(DEFAULT_VALIDATION_ARTIFACT_PATH),
                        help="Path to approved validation artifact JSON")
    parser.add_argument("--class-name", default="PodcastAlphaStrategy",
                        help="Strategy class name to generate")
    return parser.parse_args()


async def main():
    args = parse_args()
    print("--- Phase 5: Freqtrade Execution Factory ---")

    artifact = load_validation_artifact(path=__import__("pathlib").Path(args.artifact_path))
    if not artifact.approved:
        raise RuntimeError("Validation artifact is not approved. Run live_swarm.py successfully before execution.")

    family = get_strategy_family(artifact.strategy_type)
    params = family.validate_params(artifact.params)
    prompt = family.build_execution_prompt(params, args.class_name)

    print(f"\n1. Requesting Freqtrade Strategy from Agent (Family={artifact.strategy_type})...")
    result = await execution_agent.run(prompt)
    
    # Extract the code
    code = getattr(result, 'output', getattr(result, 'data', str(result)))
    
    # Clean up markdown if the LLM hallucinated it despite instructions
    if code.startswith("```python"):
        code = code[9:]
    elif code.startswith("```"):
        code = code[3:]
    if code.endswith("```"):
        code = code[:-3]
        
    code = code.strip()
    
    strategy_file = f"{args.class_name}.py"
    with open(strategy_file, "w") as f:
        f.write(code)
        
    print(f"\n✅ Successfully generated and saved Freqtrade Strategy to {strategy_file}!")
    print("2. You can now drop this file directly into your Freqtrade /user_data/strategies/ folder.")
    print("-" * 50)
    print("Preview of the generated strategy:")
    print("-" * 50)
    lines = code.split('\n')
    for line in lines[:20]:
        print(line)
    print("... (truncated)")
    print("-" * 50)
    print("\n🎉 The Strategy Factory Mock Project is Complete! 🎉")
    
if __name__ == "__main__":
    asyncio.run(main())
