import time
import json
import asyncio
from openai import OpenAI, RateLimitError, APIStatusError
from openai import AsyncOpenAI

from config import (
    DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, MODEL,
    MAX_RETRIES, RETRY_DELAY,
    SYSTEM_PROMPT, USER_PROMPT_TEMPLATE,
)

_sync_client = None
_async_client = None


def _get_sync_client() -> OpenAI:
    global _sync_client
    if _sync_client is None:
        if not DEEPSEEK_API_KEY:
            raise RuntimeError(
                "DEEPSEEK_API_KEY environment variable not set."
            )
        _sync_client = OpenAI(
            api_key=DEEPSEEK_API_KEY,
            base_url=DEEPSEEK_BASE_URL,
        )
    return _sync_client


def _get_async_client() -> AsyncOpenAI:
    global _async_client
    if _async_client is None:
        _async_client = AsyncOpenAI(
            api_key=DEEPSEEK_API_KEY,
            base_url=DEEPSEEK_BASE_URL,
        )
    return _async_client


async def extract_knowledge_graph_async(
    date_display: str, content: str, semaphore: asyncio.Semaphore
) -> dict:
    user_prompt = USER_PROMPT_TEMPLATE.format(
        date_display=date_display, content=content,
    )

    async with semaphore:
        for attempt in range(MAX_RETRIES + 1):
            try:
                client = _get_async_client()
                response = await client.chat.completions.create(
                    model=MODEL,
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": user_prompt},
                    ],
                    temperature=0.0,
                    response_format={"type": "json_object"},
                    max_tokens=4096,
                    timeout=60,
                )

                result_text = response.choices[0].message.content
                result = json.loads(result_text)

                if "nodes" not in result or "edges" not in result:
                    return {"nodes": [], "edges": []}
                return result

            except RateLimitError:
                wait = RETRY_DELAY * (2 ** attempt)
                print(f"  rate limited, waiting {wait}s...")
                if attempt < MAX_RETRIES:
                    await asyncio.sleep(wait)

            except json.JSONDecodeError:
                if attempt == 0:
                    await asyncio.sleep(0.5)
                    continue

            except APIStatusError as e:
                if e.status_code >= 500 and attempt < MAX_RETRIES:
                    await asyncio.sleep(RETRY_DELAY * (attempt + 1))
                    continue
                raise

            except Exception as e:
                if attempt < MAX_RETRIES:
                    await asyncio.sleep(RETRY_DELAY * (attempt + 1))
                else:
                    raise

    return {"nodes": [], "edges": []}
