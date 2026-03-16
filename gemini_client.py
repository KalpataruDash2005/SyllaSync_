"""
gemini_client.py
Handles all calls to the Gemini 1.5 Flash API.
  - Pass 1: summarise / structure each document's raw content
  - Pass 2: generate the full 15-week study plan as strict JSON
"""
from __future__ import annotations

import json
import logging
import os
import re
import textwrap
from typing import Any, Dict, List

import httpx
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

from models import OrganizedContent, StudyPlan

logger = logging.getLogger(__name__)

GEMINI_ENDPOINT = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    "gemini-1.5-flash:generateContent"
)

# Gemini free-tier: 15 req/min — we stay well under with retries
HTTP_TIMEOUT = 120  # seconds


class GeminiClient:
    def __init__(self) -> None:
        self.api_key = os.getenv("GEMINI_API_KEY", "AIzaSyCJB2i0sVUdu09on2zERqv42H8toSygTng")
        if not self.api_key:
            raise RuntimeError("GEMINI_API_KEY is not set in environment.")

    # ── Public API ────────────────────────────────────────────────────────

    async def summarize_content(self, organized: OrganizedContent) -> Dict[str, Any]:
        """
        Pass 1 — for each document call Gemini to extract a concise
        structured summary.  Returns a merged summary dict.
        """
        summaries: List[Dict[str, Any]] = []

        for doc in organized.documents:
            prompt = self._build_summary_prompt(doc.filename, doc.raw_text)
            raw = await self._call_gemini(prompt)
            parsed = self._parse_json(raw)
            if parsed:
                summaries.append(parsed)
            else:
                # Fallback: use heuristic topics
                summaries.append({
                    "filename": doc.filename,
                    "topics": doc.topics,
                    "key_concepts": doc.topics[:10],
                    "difficulty": "medium",
                    "estimated_pages": doc.total_pages,
                })

        return {
            "course_name": organized.course_name_guess,
            "documents": summaries,
            "all_topics": organized.combined_topics,
            "total_pages": organized.total_pages,
        }

    async def generate_study_plan(self, content_summary: Dict[str, Any]) -> Dict[str, Any]:
        """
        Pass 2 — generates the full 15-week JSON study plan
        from the content summary produced in Pass 1.
        """
        prompt = self._build_plan_prompt(content_summary)
        raw = await self._call_gemini(prompt)
        parsed = self._parse_json(raw)

        if not parsed:
            logger.error("Gemini returned non-JSON for plan: %s", raw[:500])
            raise ValueError("Gemini did not return valid JSON for study plan.")

        # Validate with Pydantic (lenient — add defaults for missing fields)
        return self._validate_plan(parsed, content_summary)

    # ── Prompt Builders ──────────────────────────────────────────────────

    @staticmethod
    def _build_summary_prompt(filename: str, raw_text: str) -> str:
        return textwrap.dedent(f"""
        You are an expert academic content analyser.
        Analyse the following extracted text from the file "{filename}" and return ONLY a JSON object
        — no markdown, no explanation, no code fences.

        JSON schema (fill every field):
        {{
          "filename": "{filename}",
          "document_type": "<syllabus|textbook|lecture_notes|assignment|other>",
          "inferred_course_name": "<string>",
          "main_subject_area": "<string>",
          "difficulty_level": "<beginner|intermediate|advanced>",
          "key_topics": ["<topic1>", "<topic2>", ...],        // max 20
          "chapters_or_sections": ["<ch1>", "<ch2>", ...],   // as listed
          "important_dates": ["<event: date>", ...],
          "prerequisites": ["<subject>", ...],
          "assignments_mentioned": ["<assignment description>", ...],
          "exam_info": "<string describing exams if found>",
          "estimated_weekly_content_hours": <integer 5-20>
        }}

        --- BEGIN DOCUMENT TEXT ---
        {raw_text[:60000]}
        --- END DOCUMENT TEXT ---
        """).strip()

    @staticmethod
    def _build_plan_prompt(content: Dict[str, Any]) -> str:
        docs_json = json.dumps(content.get("documents", []), indent=2)
        course = content.get("course_name", "My Course")

        return textwrap.dedent(f"""
        You are SyllabSync, an expert academic study-plan architect.
        Based on the structured course content summaries below,
        create a comprehensive, personalized 15-week study plan.

        Return ONLY a single valid JSON object — no markdown, no fences, no extra text.

        Course Name: {course}
        Content Summaries:
        {docs_json}

        Output JSON schema — every field is REQUIRED:
        {{
          "course_name": "<string>",
          "semester_duration_weeks": 15,
          "total_study_hours_per_week": <int>,
          "difficulty_level": "<Beginner|Intermediate|Advanced>",
          "prerequisites": ["<string>"],
          "weeks": [
            {{
              "week_number": <1-15>,
              "theme": "<weekly theme>",
              "topics": ["<topic>"],
              "learning_objectives": ["<objective>"],
              "study_hours": <int>,
              "difficulty": <1-5>,
              "daily_schedule": {{
                "Monday":    {{"duration_min": <int>, "activity": "<string>", "technique": "<string>"}},
                "Tuesday":   {{"duration_min": <int>, "activity": "<string>", "technique": "<string>"}},
                "Wednesday": {{"duration_min": <int>, "activity": "<string>", "technique": "<string>"}},
                "Thursday":  {{"duration_min": <int>, "activity": "<string>", "technique": "<string>"}},
                "Friday":    {{"duration_min": <int>, "activity": "<string>", "technique": "<string>"}},
                "Saturday":  {{"duration_min": <int>, "activity": "<string>", "technique": "<string>"}},
                "Sunday":    {{"duration_min": 0,   "activity": "Rest & light review", "technique": "Rest"}}
              }},
              "memory_techniques": [
                {{"name": "<technique>", "description": "<how to apply for this week's topics>"}}
              ],
              "study_tips": ["<tip>"],
              "resources": ["<chapter / lecture / reading>"],
              "assignments_due": ["<description or empty list>"],
              "exam_weight": "<percentage or empty string>"
            }}
          ],
          "global_memory_techniques": {{
            "spaced_repetition": {{"description": "<>", "tools": ["Anki","Quizlet"], "schedule": "<>"}},
            "pomodoro":          {{"description": "<>", "work_min": 25, "break_min": 5, "tips": ["<>"]}},
            "mind_mapping":      {{"description": "<>", "tools": ["MindMeister","XMind"], "tips": ["<>"]}},
            "feynman_technique": {{"description": "<>", "steps": ["<>"]}},
            "cornell_notes":     {{"description": "<>", "sections": ["Cue","Notes","Summary"]}},
            "active_recall":     {{"description": "<>", "methods": ["<>"]}}
          }},
          "exam_preparation": {{
            "weeks_before_exam": 3,
            "strategy": "<string>",
            "daily_breakdown": ["<day N: activity>"]
          }},
          "study_environment_tips": ["<tip>"],
          "productivity_hacks": ["<hack>"],
          "mental_health_tips": ["<tip>"]
        }}
        """).strip()

    # ── Gemini HTTP Call ─────────────────────────────────────────────────

    @retry(
        stop=stop_after_attempt(4),
        wait=wait_exponential(multiplier=2, min=4, max=30),
        retry=retry_if_exception_type((httpx.HTTPStatusError, httpx.TimeoutException)),
    )
    async def _call_gemini(self, prompt: str) -> str:
        url = f"{GEMINI_ENDPOINT}?key={self.api_key}"
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.3,
                "maxOutputTokens": 8192,
            },
        }

        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()

        data = resp.json()
        try:
            return data["candidates"][0]["content"]["parts"][0]["text"]
        except (KeyError, IndexError) as exc:
            raise ValueError(f"Unexpected Gemini response shape: {data}") from exc

    # ── Helpers ──────────────────────────────────────────────────────────

    @staticmethod
    def _parse_json(raw: str) -> Dict[str, Any] | None:
        """Strip markdown fences and parse JSON safely."""
        # Remove ```json ... ``` or ``` ... ```
        cleaned = re.sub(r"^```(?:json)?\s*", "", raw.strip(), flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*```$", "", cleaned.strip())

        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            # Try to extract first JSON object from mixed content
            match = re.search(r"\{.*\}", cleaned, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group())
                except json.JSONDecodeError:
                    pass
        return None

    @staticmethod
    def _validate_plan(raw: Dict[str, Any], content: Dict[str, Any]) -> Dict[str, Any]:
        """
        Light validation + default injection so the frontend never
        crashes on missing keys.
        """
        raw.setdefault("course_name", content.get("course_name", "My Course"))
        raw.setdefault("semester_duration_weeks", 15)
        raw.setdefault("total_study_hours_per_week", 12)
        raw.setdefault("difficulty_level", "Intermediate")
        raw.setdefault("prerequisites", [])
        raw.setdefault("weeks", [])
        raw.setdefault("study_environment_tips", [])
        raw.setdefault("productivity_hacks", [])
        raw.setdefault("mental_health_tips", [])

        # Ensure exactly 15 weeks
        existing = {w.get("week_number"): w for w in raw["weeks"]}
        weeks = []
        for n in range(1, 16):
            if n in existing:
                weeks.append(existing[n])
            else:
                weeks.append({
                    "week_number": n,
                    "theme": f"Week {n} — Study Block",
                    "topics": ["Review and consolidation"],
                    "learning_objectives": ["Consolidate previous material"],
                    "study_hours": 10,
                    "difficulty": 3,
                    "daily_schedule": {
                        d: {"duration_min": 60, "activity": "Self-study", "technique": "Active Recall"}
                        for d in ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]
                    },
                    "memory_techniques": [{"name": "Spaced Repetition", "description": "Review flashcards"}],
                    "study_tips": ["Focus on weak areas"],
                    "resources": [],
                    "assignments_due": [],
                    "exam_weight": "",
                })
        raw["weeks"] = weeks
        return raw
