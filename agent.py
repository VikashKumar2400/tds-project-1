import json
import os
import re
import time
from typing import Dict, List, Optional
from urllib.parse import urlparse

import requests
from openai import OpenAI

from config import AIPIPE_API_KEY, MODEL


# ============================================================
# AI CLIENT
# ============================================================

def _get_client() -> OpenAI:
    api_key = AIPIPE_API_KEY or os.getenv("AIPIPE_TOKEN")

    if not api_key:
        raise ValueError(
            "AIPIPE_API_KEY or AIPIPE_TOKEN must be set"
        )

    return OpenAI(
        base_url="https://aipipe.org/openai/v1",
        api_key=api_key,
    )


# ============================================================
# SYSTEM PROMPT
# ============================================================

SYSTEM_PROMPT = """
You are a careful data analyst.

The user's LAST message contains the question that must be answered.

IMPORTANT:

1. Answer the LAST user message.
2. Previous messages are context only.
3. Use previous messages when the last question depends on them.
4. The user's LAST message specifies the exact JSON shape.
5. Follow that JSON shape exactly.
6. Return ONLY one valid JSON object.
7. Do not use Markdown.
8. Do not use code fences.
9. Do not add explanations.
10. Do not add extra keys.
11. Do not automatically add "answer".
12. Do not automatically add "log_url".
13. If the requested shape is {"value": ...}, return {"value": ...}.
14. If the requested shape contains {"answer": ..., "log_url": ...},
    return that requested structure.
15. Preserve nested objects.
16. Preserve list order.
17. Preserve exact integer values.
18. Apply the requested rounding.
19. For population standard deviation, divide by N, not N-1.
20. When external data is supplied below, use that data rather than guessing.
21. Never output anything outside the JSON object.

EXTERNAL DATA MAY APPEAR BELOW THE USER QUESTION.
"""


# ============================================================
# URL HELPERS
# ============================================================

def _extract_urls(text: str) -> List[str]:
    """
    Extract HTTP/HTTPS URLs from a message.
    """

    urls = re.findall(
        r'https?://[^\s<>"\']+',
        text,
    )

    # Remove punctuation that may follow a URL.
    cleaned = []

    for url in urls:
        url = url.rstrip(".,;:)]}")

        if url not in cleaned:
            cleaned.append(url)

    return cleaned


def _is_github_api_repo_url(url: str) -> bool:
    """
    Check whether URL looks like:

    https://api.github.com/repos/OWNER/REPO
    """

    parsed = urlparse(url)

    return (
        parsed.netloc.lower() == "api.github.com"
        and parsed.path.lower().startswith("/repos/")
    )


def _github_headers() -> Dict[str, str]:
    """
    GitHub recommends Accept + API version + User-Agent.
    """

    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2026-03-10",
        "User-Agent": "TDS-Data-Analyst-Bot",
    }

    # Optional GitHub token.
    #
    # If you put GITHUB_TOKEN in Render environment variables,
    # authenticated requests get a much higher rate limit.
    token = os.getenv("GITHUB_TOKEN")

    if token:
        headers["Authorization"] = f"Bearer {token}"

    return headers


def _fetch_github_repo(url: str) -> str:
    """
    Fetch a GitHub repository.

    First try the GitHub REST API.

    If the API returns a rate-limit/403 response, try the
    normal GitHub repository HTML page as a fallback and
    extract the repository ID from its metadata.
    """

    headers = _github_headers()

    # --------------------------------------------------------
    # Attempt 1: GitHub REST API
    # --------------------------------------------------------

    for attempt in range(2):

        try:

            response = requests.get(
                url,
                headers=headers,
                timeout=15,
            )

            print(
                "GitHub API:",
                response.status_code,
                response.url,
            )

            # Successful JSON response.
            if response.status_code == 200:

                try:
                    data = response.json()

                    # Return only useful repository information.
                    # This reduces the amount of text sent to the LLM.
                    useful = {
                        "id": data.get("id"),
                        "name": data.get("name"),
                        "full_name": data.get("full_name"),
                        "description": data.get("description"),
                        "html_url": data.get("html_url"),
                        "private": data.get("private"),
                    }

                    return json.dumps(
                        useful,
                        ensure_ascii=False,
                    )

                except Exception:
                    return response.text[:30000]

            # ------------------------------------------------
            # 403: possibly rate limit.
            # Retry once if Retry-After exists.
            # ------------------------------------------------

            if response.status_code == 403:

                retry_after = response.headers.get(
                    "Retry-After"
                )

                if retry_after and attempt == 0:

                    try:
                        delay = min(
                            int(retry_after),
                            5,
                        )

                        time.sleep(delay)

                    except Exception:
                        pass

                    continue

                # Stop API attempts and use HTML fallback.
                break

            # Other status.
            break

        except Exception as e:

            print(
                "GitHub API error:",
                type(e).__name__,
                str(e),
            )

            break

    # --------------------------------------------------------
    # Attempt 2: normal GitHub repository page
    # --------------------------------------------------------

    parsed = urlparse(url)

    parts = [
        p
        for p in parsed.path.split("/")
        if p
    ]

    if len(parts) >= 3 and parts[0].lower() == "repos":

        owner = parts[1]
        repo = parts[2]

        html_url = (
            f"https://github.com/{owner}/{repo}"
        )

        try:

            response = requests.get(
                html_url,
                headers={
                    "User-Agent": "TDS-Data-Analyst-Bot"
                },
                timeout=15,
            )

            print(
                "GitHub HTML fallback:",
                response.status_code,
            )

            html = response.text

            # Common GitHub repository metadata.
            patterns = [
                r'name=["\']octolytics-dimension-repository_id["\']'
                r'\s+content=["\'](\d+)["\']',

                r'content=["\'](\d+)["\']'
                r'\s+name=["\']octolytics-dimension-repository_id["\']',

                r'name=["\']hovercard-subject-tag["\']'
                r'\s+content=["\']repository:(\d+)["\']',

                r'"repository_id"\s*:\s*(\d+)',

                r'"id"\s*:\s*(\d+)'
                r'.{0,100}"full_name"\s*:\s*"'
                + re.escape(owner)
                + r"/"
                + re.escape(repo)
                + r'"',
            ]

            for pattern in patterns:

                match = re.search(
                    pattern,
                    html,
                    flags=re.IGNORECASE | re.DOTALL,
                )

                if match:

                    repo_id = int(match.group(1))

                    return json.dumps(
                        {
                            "id": repo_id,
                            "full_name": f"{owner}/{repo}",
                            "source": "github-html-fallback",
                        },
                        ensure_ascii=False,
                    )

        except Exception as e:

            print(
                "GitHub HTML fallback error:",
                type(e).__name__,
                str(e),
            )

    return json.dumps(
        {
            "error": "Unable to fetch GitHub repository data",
            "url": url,
        },
        ensure_ascii=False,
    )


def _fetch_normal_url(url: str) -> str:
    """
    Fetch a normal public URL.
    """

    headers = {
        "User-Agent": "TDS-Data-Analyst-Bot/1.0",
        "Accept": "*/*",
    }

    try:

        response = requests.get(
            url,
            headers=headers,
            timeout=20,
        )

        print(
            "URL FETCH:",
            response.status_code,
            response.url,
        )

        content_type = (
            response.headers
            .get("content-type", "")
            .lower()
        )

        # JSON
        if "json" in content_type:

            try:

                data = response.json()

                return json.dumps(
                    data,
                    ensure_ascii=False,
                )[:50000]

            except Exception:

                return response.text[:50000]

        # CSV / text / HTML
        return response.text[:50000]

    except Exception as e:

        return json.dumps(
            {
                "error": (
                    f"{type(e).__name__}: {str(e)}"
                ),
                "url": url,
            },
            ensure_ascii=False,
        )


def _fetch_url(url: str) -> str:
    """
    Fetch one public URL.
    """

    if _is_github_api_repo_url(url):
        return _fetch_github_repo(url)

    return _fetch_normal_url(url)


def _get_external_data(prompt: str) -> str:
    """
    Fetch URLs explicitly present in the question.
    """

    urls = _extract_urls(prompt)

    if not urls:
        return ""

    sections = []

    for url in urls[:5]:

        print(
            "===== FETCHING URL ====="
        )

        print(url)

        content = _fetch_url(url)

        sections.append(
            "\n"
            "EXTERNAL SOURCE URL:\n"
            f"{url}\n\n"
            "EXTERNAL SOURCE CONTENT:\n"
            f"{content}\n"
        )

    return "\n".join(sections)


# ============================================================
# LLM
# ============================================================

def ask_llm(
    prompt: str,
    history: Optional[List[Dict[str, str]]] = None,
) -> str:

    client = _get_client()

    messages = [
        {
            "role": "system",
            "content": SYSTEM_PROMPT,
        }
    ]

    # Previous conversation.
    if history:

        messages.extend(
            history[-12:]
        )

    # Fetch URLs from the CURRENT message.
    external_data = _get_external_data(prompt)

    current_prompt = prompt

    if external_data:

        current_prompt += (
            "\n\n"
            "===== EXTERNAL DATA =====\n"
            + external_data
            + "\n===== END EXTERNAL DATA ====="
        )

    messages.append(
        {
            "role": "user",
            "content": current_prompt,
        }
    )

    print(
        "===== LLM REQUEST ====="
    )

    print(
        "MODEL:",
        MODEL,
    )

    print(
        "PROMPT:",
        current_prompt,
    )

    try:

        # IMPORTANT:
        # Do NOT set temperature=0.
        # gpt-5-mini through this endpoint only supports
        # the default temperature.
        response = client.chat.completions.create(
            model=MODEL,
            messages=messages,
        )

        content = (
            response.choices[0]
            .message
            .content
            or ""
        )

        print(
            "===== LLM RESPONSE ====="
        )

        print(
            repr(content)
        )

        print(
            "========================"
        )

        return content.strip()

    except Exception as e:

        print(
            "===== LLM ERROR ====="
        )

        print(
            type(e).__name__
        )

        print(
            str(e)
        )

        print(
            "====================="
        )

        raise