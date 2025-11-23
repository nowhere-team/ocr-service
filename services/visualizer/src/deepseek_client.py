import json
import time
from pathlib import Path
from typing import Any

import requests

from .config import settings


class DeepSeekClient:
    """client for deepseek api text structuring"""

    def __init__(self):
        self.api_url = settings.deepseek_api_url
        self.api_key = settings.deepseek_api_key
        self.session = requests.Session()

        # load system prompt from txt
        prompt_file = Path(__file__).parent.parent / "prompt.txt"
        with prompt_file.open("r", encoding="utf-8") as f:
            self.system_prompt = f.read()

    def structure_text(
        self, raw_text: str, max_retries: int = 3, timeout: int = 60
    ) -> dict[str, Any] | None:
        """
        structure raw ocr text using deepseek api with retry logic

        args:
            raw_text: unstructured text from ocr
            max_retries: number of retry attempts
            timeout: request timeout in seconds

        returns:
            structured data dict or none if failed
        """
        if not self.api_key:
            return {"error": "deepseek api key not configured"}

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

        payload = {
            "model": "deepseek-chat",
            "messages": [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": raw_text},
            ],
            "temperature": 0.1,
            "max_tokens": 2000,
        }

        last_error = None

        for attempt in range(max_retries):
            try:
                response = self.session.post(
                    self.api_url, headers=headers, json=payload, timeout=timeout
                )

                if response.status_code == 200:
                    result = response.json()
                    content = result["choices"][0]["message"]["content"]

                    # extract json from response (may be wrapped in markdown)
                    content = content.strip()
                    if content.startswith("```json"):
                        content = content[7:]
                    if content.startswith("```"):
                        content = content[3:]
                    if content.endswith("```"):
                        content = content[:-3]
                    content = content.strip()

                    structured = json.loads(content)
                    return structured

                elif response.status_code == 429:
                    # rate limit - wait and retry
                    wait_time = 2**attempt
                    time.sleep(wait_time)
                    last_error = f"rate limit (attempt {attempt + 1}/{max_retries})"
                    continue

                else:
                    last_error = f"api error {response.status_code}: {response.text[:200]}"
                    # don't retry on 4xx errors except 429
                    if 400 <= response.status_code < 500 and response.status_code != 429:
                        break

            except requests.exceptions.Timeout:
                last_error = f"timeout after {timeout}s (attempt {attempt + 1}/{max_retries})"
                # retry on timeout with exponential backoff
                if attempt < max_retries - 1:
                    wait_time = 2**attempt
                    time.sleep(wait_time)
                continue

            except json.JSONDecodeError as e:
                return {"error": "failed to parse api response", "details": str(e)}

            except Exception as e:
                last_error = f"request failed: {str(e)}"
                # retry on connection errors
                if attempt < max_retries - 1:
                    wait_time = 2**attempt
                    time.sleep(wait_time)
                continue

        # all retries failed
        return {"error": "api request failed after retries", "details": last_error}
