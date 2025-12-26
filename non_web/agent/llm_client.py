import google.generativeai as genai

class LLMClient:
    def __init__(self, api_key: str):
        genai.configure(api_key=api_key)
        # Use gemini-2.5-flash for fast, capable AI reasoning
        # Other options: gemini-2.5-pro (more powerful), gemini-pro-latest (always latest)
        self.model = genai.GenerativeModel("models/gemini-2.5-flash")

    def ask(self, prompt: str):
        try:
            response = self.model.generate_content(
                prompt,
                generation_config={"temperature": 0.2}
            )
            return response.text
        except Exception as e:
            print(f"[ERROR] LLM API call failed: {e}")
            raise
