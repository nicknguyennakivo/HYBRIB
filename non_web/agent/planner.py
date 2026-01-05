import json
import re
from datetime import datetime

class Planner:
    def __init__(self, llm: "LLMClient"):
        self.llm = llm

    def create_plan(self, testcase_text: str) -> dict:
        prompt = f"""
You are a senior automation planner.

CRITICAL RULES (must follow):
- Preserve ALL literals EXACTLY as written in the testcase.
- Do NOT redact, abstract, paraphrase, or hide credentials.
- Strings inside quotes MUST appear unchanged in output.
- Do NOT replace passwords with generic wording.

Convert the following testcase into a PLANNED GOAL and REQUIRED STEPS.

Testcase:
{testcase_text}

Return ONLY valid JSON in this exact format:
{{
  "goal": "string",
  "steps": ["step1", "step2"]
}}
"""
        result = self.llm.ask(prompt)
        print(f"[DEBUG] [{datetime.now().strftime('%H:%M:%S')}] Planner raw response:\n{result}\n")
        
        # Extract JSON from markdown code blocks if present
        json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', result, re.DOTALL)
        if json_match:
            result = json_match.group(1)
        
        # Clean up the result
        result = result.strip()
        
        try:
            return json.loads(result)
        except json.JSONDecodeError as e:
            print(f"[ERROR] Failed to parse JSON: {e}")
            print(f"[ERROR] Raw response was: {result}")
            raise
