import os
import httpx
import uuid
import asyncio

# Get API key and endpoint from environment variables
TRANSLATOR_API_KEY = os.environ.get("TRANSLATOR_API_KEY")
TRANSLATOR_ENDPOINT = "https://api.cognitive.microsofttranslator.com/"
TRANSLATOR_LOCATION = os.environ.get("TRANSLATOR_LOCATION", "global")

async def translate_text(text: str) -> str:
    """Translates text to English using Microsoft Translator API, with chunking and retry logic."""
    if not TRANSLATOR_API_KEY:
        raise ValueError("TRANSLATOR_API_KEY environment variable not set.")

    # Increased chunk size to reduce the number of requests
    CHUNK_SIZE = 4800
    text_chunks = [text[i:i + CHUNK_SIZE] for i in range(0, len(text), CHUNK_SIZE)]
    
    translated_chunks = []
    MAX_RETRIES = 3

    async with httpx.AsyncClient() as client:
        for chunk in text_chunks:
            headers = {
                'Ocp-Apim-Subscription-Key': TRANSLATOR_API_KEY,
                'Ocp-Apim-Subscription-Region': TRANSLATOR_LOCATION,
                'Content-type': 'application/json',
                'X-ClientTraceId': str(uuid.uuid4())
            }
            params = {
                'api-version': '3.0',
                'to': 'en'
            }
            body = [{'text': chunk}]

            for attempt in range(MAX_RETRIES):
                try:
                    response = await client.post(f"{TRANSLATOR_ENDPOINT}/translate", params=params, headers=headers, json=body)
                    response.raise_for_status()
                    
                    translation_result = response.json()
                    translated_chunks.append(translation_result[0]['translations'][0]['text'])
                    
                    # If successful, break the retry loop and add a small delay before the next chunk
                    await asyncio.sleep(1)
                    break
                except httpx.HTTPStatusError as e:
                    if e.response.status_code == 429 and attempt < MAX_RETRIES - 1:
                        # Exponential backoff: wait 2, 4 seconds
                        wait_time = 2 ** (attempt + 1)
                        print(f"Rate limit hit. Retrying in {wait_time} seconds...")
                        await asyncio.sleep(wait_time)
                    else:
                        # For other errors or if max retries are reached, re-raise the exception
                        raise e
    
    return "".join(translated_chunks)
