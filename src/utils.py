import asyncio
from openai import AsyncOpenAI
from pydantic_ai.models.openai import OpenAIChatModel, OpenAIChatModelSettings
from pydantic_ai.providers.openai import OpenAIProvider
import tiktoken

import config


enc = tiktoken.encoding_for_model("gpt-4")

def truncate_tokens(text: str) -> str:
    """
    Count the number of tokens in a text.
    """
    tokens = enc.encode(text)

    # count tokens
    length = len(tokens)

    if length > config.MAX_TOKENS_PER_TOOL_RESPONSE:
        # truncate the text
        text = enc.decode(tokens[:config.MAX_TOKENS_PER_TOOL_RESPONSE])
        text += "\n... [truncated because it exceeds the max tokens limit, try deeper paths]"

    return text

def get_llm(model: str = None) -> OpenAIChatModel:
    """Initialize and return the specified LLM"""

    model = model or config.MODEL

    model = OpenAIChatModel(
        model_name=model,
        provider=OpenAIProvider(
            base_url=config.BASE_URL,
            api_key=config.API_KEY
        ),
        settings=OpenAIChatModelSettings(
            temperature=0.0,
            max_tokens=36000,
            timeout=300
        )
    )

    return model
    
async def run_llm_natively(model: str = None, prompt: str = None, messages: list[dict] = None) -> str:
    client = AsyncOpenAI(
        base_url=config.BASE_URL,
        api_key=config.API_KEY,
    )

    if messages is None:
        messages = [{"role": "user", "content": prompt}]

    response = await client.chat.completions.create(
        model=model or config.MODEL,
        messages=messages,
    )

    return response.choices[0].message.content

if __name__ == "__main__":
    result = asyncio.run(run_llm_natively(model="gpt-oss-120b", messages=[{"role": "system", "content": "You are a helpful assistant."}, {"role": "user", "content": "Hello, world!"}]))
    print(result)

# ------------------------------------------------------------
# Embeddings
# ------------------------------------------------------------

async def get_embeddings(texts: list[str]) -> list[list[float]]:
    client = AsyncOpenAI(
        base_url=config.BASE_URL,
        api_key=config.API_KEY,
    )
    response = await client.embeddings.create(
        input=texts,
        model=config.EMBEDDING_MODEL,
    )

    return [embedding.embedding for embedding in response.data]



