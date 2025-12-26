import json
import google.generativeai as genai
import os
from dotenv import load_dotenv

load_dotenv()

class AIDomLocatorAgent:

    def __init__(self):
        api_key = os.getenv("GEMINI_API_KEY")
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel("models/gemini-2.5-flash")

    def generate_locator(self, html_snapshot: str, target_description: str):
        """
        Input:
            html_snapshot → full DOM HTML
            target_description → user's natural language description
        Output:
            dictionary with CSS, XPath, Playwright Locator suggestions
        """

        prompt = f"""
You are an expert DOM analyzer. 
Given the DOM snapshot and element description, generate possible selectors.

Rules:
- Prefer stable CSS selectors
- Avoid auto-generated dynamic IDs
- Prioritize data-testid, role, aria-label, text
- Generate Playwright locators: get_by_role(), get_by_text(), locator()
- Provide 5 strongest candidates sorted by reliability

Target: "{target_description}"

HTML:
{html_snapshot}

Return ONLY JSON in this format:
{{
  "playwright_locators": [...],
  "css_selectors": [...],
  "xpath_selectors": [...],
  "best_guess": "..."
}}
"""

        try:
            response = self.model.generate_content(
                prompt,
                generation_config={"temperature": 0}
            )
            result = response.text.strip()
            
            # Extract JSON from markdown code blocks if present
            import re
            json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', result, re.DOTALL)
            if json_match:
                result = json_match.group(1)
            
            return json.loads(result)
        except Exception as e:
            print(f"[ERROR] AI Locator generation failed: {e}")
            raise
