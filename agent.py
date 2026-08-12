import json
import os
import re
import time
from datetime import datetime, timezone
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
    GitHub request headers.
    """

    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2026-03-10",
        "User-Agent": "TDS-Data-Analyst-Bot",
    }

    token = os.getenv("GITHUB_TOKEN")

    if token:
        headers["Authorization"] = f"Bearer {token}"

    return headers


def _fetch_github_repo(url: str) -> str:
    """
    Fetch a GitHub repository.

    First try the GitHub REST API.

    If the API returns a rate-limit/403 response,
    try the normal GitHub repository HTML page.
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

            if response.status_code == 200:

                try:

                    data = response.json()

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

                break

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
# USGS EARTHQUAKE SOLVER
# ============================================================

def _is_usgs_earthquake_question(prompt: str) -> bool:
    """
    Detect USGS earthquake catalog questions.
    """

    text = prompt.lower()

    return (
        "usgs" in text
        and "earthquake" in text
        and "earthquake catalog" in text
    )


def _extract_min_magnitude(prompt: str) -> float:
    """
    Extract minimum magnitude from questions such as:

    magnitude 5.0 or greater
    magnitude 5 or greater
    magnitude >= 5
    magnitude 5+
    """

    patterns = [
        r"magnitude\s*(?:of\s*)?(\d+(?:\.\d+)?)\s*or\s*greater",
        r"magnitude\s*(?:of\s*)?(\d+(?:\.\d+)?)\s*or\s*more",
        r"magnitude\s*(?:>=|≥)\s*(\d+(?:\.\d+)?)",
        r"magnitude\s*(\d+(?:\.\d+)?)\s*\+",
    ]

    for pattern in patterns:

        match = re.search(
            pattern,
            prompt,
            flags=re.IGNORECASE,
        )

        if match:
            return float(match.group(1))

    raise ValueError(
        "Could not determine the minimum earthquake magnitude "
        "from the question."
    )


def _extract_month_year(prompt: str):
    """
    Extract month and year from questions such as:

    in June 2023
    during June 2023
    June 2023
    """

    months = {
        "january": 1,
        "february": 2,
        "march": 3,
        "april": 4,
        "may": 5,
        "june": 6,
        "july": 7,
        "august": 8,
        "september": 9,
        "october": 10,
        "november": 11,
        "december": 12,
    }

    pattern = (
        r"\b("
        + "|".join(months.keys())
        + r")\s+(\d{4})\b"
    )

    match = re.search(
        pattern,
        prompt,
        flags=re.IGNORECASE,
    )

    if not match:
        raise ValueError(
            "Could not determine the month and year "
            "from the question."
        )

    month_name = match.group(1).lower()
    year = int(match.group(2))
    month = months[month_name]

    return year, month


def _next_month(year: int, month: int):
    """
    Return the next calendar month.
    """

    if month == 12:
        return year + 1, 1

    return year, month + 1


def _solve_usgs_earthquake_question(prompt: str) -> str:
    """
    Solve questions asking:

    Among earthquakes above a magnitude threshold
    in a particular month, which UTC calendar date
    has the largest range between highest and lowest
    earthquake magnitude?

    Data source:
    USGS Earthquake Catalog API.
    """

    min_magnitude = _extract_min_magnitude(prompt)

    year, month = _extract_month_year(prompt)

    next_year, next_month = _next_month(
        year,
        month,
    )

    start_date = (
        f"{year:04d}-{month:02d}-01T00:00:00"
    )

    end_date = (
        f"{next_year:04d}-{next_month:02d}-01T00:00:00"
    )

    url = (
        "https://earthquake.usgs.gov/"
        "fdsnws/event/1/query"
    )

    params = {
        "format": "geojson",
        "starttime": start_date,
        "endtime": end_date,
        "minmagnitude": min_magnitude,
        "eventtype": "earthquake",
        "orderby": "time-asc",
        "limit": 20000,
    }

    print(
        "===== USGS EARTHQUAKE QUERY ====="
    )

    print("URL:", url)
    print("PARAMS:", params)

    response = requests.get(
        url,
        params=params,
        timeout=30,
    )

    print(
        "USGS STATUS:",
        response.status_code,
    )

    response.raise_for_status()

    data = response.json()

    features = data.get(
        "features",
        [],
    )

    print(
        "USGS EVENTS:",
        len(features),
    )

    if not features:
        raise ValueError(
            "USGS returned no earthquakes matching the query."
        )

    # --------------------------------------------------------
    # Group magnitudes by UTC calendar date
    # --------------------------------------------------------

    daily_magnitudes = {}

    for feature in features:

        properties = feature.get(
            "properties",
            {},
        )

        magnitude = properties.get(
            "mag"
        )

        timestamp = properties.get(
            "time"
        )

        if magnitude is None:
            continue

        if timestamp is None:
            continue

        # USGS timestamps are milliseconds since Unix epoch.
        utc_datetime = datetime.fromtimestamp(
            timestamp / 1000,
            tz=timezone.utc,
        )

        date = utc_datetime.date().isoformat()

        daily_magnitudes.setdefault(
            date,
            [],
        ).append(
            float(magnitude)
        )

    if not daily_magnitudes:
        raise ValueError(
            "No usable earthquake magnitude data was returned."
        )

    # --------------------------------------------------------
    # Find date with widest magnitude range
    # --------------------------------------------------------

    best_date = None
    best_range = float("-inf")

    for date in sorted(daily_magnitudes):

        magnitudes = daily_magnitudes[date]

        highest = max(magnitudes)
        lowest = min(magnitudes)

        magnitude_range = (
            highest - lowest
        )

        print(
            f"USGS {date}: "
            f"highest={highest}, "
            f"lowest={lowest}, "
            f"range={magnitude_range}"
        )

        # Using > means the first date wins in the
        # extremely unlikely event of an exact tie.
        if magnitude_range > best_range:

            best_range = magnitude_range
            best_date = date

    if best_date is None:
        raise ValueError(
            "Could not determine the date with the widest range."
        )

    print(
        "===== USGS ANSWER ====="
    )

    print(
        "DATE:",
        best_date,
    )

    print(
        "RANGE:",
        best_range,
    )

    # Return the structure expected by the TDS bot.
    return json.dumps(
        {
            "answer": {
                "date": best_date
            },
            "log_url": (
                "https://example.com/agent_log.jsonl"
            ),
        },
        ensure_ascii=False,
    )


# ============================================================
# LLM
# ============================================================

def ask_llm(
    prompt: str,
    history: Optional[List[Dict[str, str]]] = None,
) -> str:

    # ========================================================
    # SPECIAL DATA SOURCE:
    # USGS EARTHQUAKE CATALOG
    # ========================================================

    if _is_usgs_earthquake_question(prompt):

        print(
            "===== USGS QUESTION DETECTED ====="
        )

        try:

            return _solve_usgs_earthquake_question(
                prompt
            )

        except Exception as e:

            print(
                "===== USGS ERROR ====="
            )

            print(
                type(e).__name__
            )

            print(
                str(e)
            )

            print(
                "======================"
            )

            # Do not silently return an empty date.
            # Fall back to the LLM only if the direct
            # USGS query failed.
            #
            # This allows the rest of the application
            # to continue working.

    # ========================================================
    # NORMAL LLM PATH
    # ========================================================

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

    # Fetch URLs from CURRENT message.
    external_data = _get_external_data(
        prompt
    )

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

        # Do NOT set temperature=0.
        # gpt-5-mini through this endpoint only
        # supports the default temperature.

        response = client.chat.completions.create(
            model=MODEL,
            messages=messages,
        )

        content = (
            response
            .choices[0]
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