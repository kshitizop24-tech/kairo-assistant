import os
import requests
from dotenv import load_dotenv

load_dotenv()

KIMI_API_KEY = os.getenv("KIMI_API_KEY")
KIMI_BASE_URL = "https://api.moonshot.ai/v1"


class KimiConnector:

    def __init__(self, model="kimi-k3.1-pro"):
        self.model = model

    def generate_response(self, prompt):

        if not KIMI_API_KEY:
            return "Error: KIMI_API_KEY not found in .env"

        try:
            response = requests.post(
                f"{KIMI_BASE_URL}/chat/completions",
                headers={
                    "Authorization": f"Bearer {KIMI_API_KEY}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "user", "content": prompt}
                    ],
                    "stream": False
                },
                timeout=120
            )

            response.raise_for_status()

            return response.json()["choices"][0]["message"]["content"]

        except requests.RequestException as error:
            return f"Kimi request failed: {error}"