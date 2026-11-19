
import os
import requests
from dotenv import load_dotenv

load_dotenv(
    dotenv_path=os.path.join(
        os.path.dirname(__file__), "..", ".env"
    )
)

OLLAMA_URL = "http://localhost:11434"
KIMI_API_URL = "https://api.moonshot.ai/v1/chat/completions"


class ModelManager:

    def __init__(self):
        self.current_provider = "ollama"
        self.current_model = "deepseek-r1:8b"

    def set_model(self, model_name, provider="ollama"):
        self.current_model = model_name
        self.current_provider = provider

    def get_available_models(self):
        try:
            response = requests.get(
                f"{OLLAMA_URL}/api/tags",
                timeout=10
            )
            response.raise_for_status()

            models = response.json().get("models", [])
            return [model["name"] for model in models]

        except requests.RequestException as error:
            print(f"Could not connect to Ollama: {error}")
            return []

    def generate_response(self, prompt):

        if self.current_provider == "kimi":
            return self._generate_kimi(prompt)

        return self._generate_ollama(prompt)

    def _generate_kimi(self, prompt):

        api_key = os.getenv("KIMI_API_KEY")

        if not api_key:
            return "Error: KIMI_API_KEY not found in .env"

        try:
            response = requests.post(
                KIMI_API_URL,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": self.current_model,
                    "messages": [
                        {"role": "user", "content": prompt}
                    ],
                    "temperature": 0.6
                },
                timeout=1200
            )

            response.raise_for_status()

            return response.json()["choices"][0]["message"]["content"]

        except requests.HTTPError as error:
            response = error.response

            print("Kimi HTTP Status:", response.status_code)
            print("Kimi Error Details:", response.text)
            print("Retry After:", response.headers.get("Retry-After"))

            return f"Kimi request failed: {response.status_code}"

        except requests.RequestException as error:
            return f"Kimi connection failed: {error}"

    def _generate_ollama(self, prompt):

        try:
            response = requests.post(
                f"{OLLAMA_URL}/api/chat",
                json={
                    "model": self.current_model,
                    "messages": [
                        {"role": "user", "content": prompt}
                    ],
                    "stream": False
                },
                timeout=1200
            )

            response.raise_for_status()

            return response.json()["message"]["content"]
        except requests.HTTPError as error:
            response = error.response

            print("Kimi HTTP Status:", response.status_code)
            print("Kimi Error Details:", response.text)
            print("Retry After:", response.headers.get("Retry-After"))

            return f"Kimi request failed: {response.status_code}"

        except requests.RequestException as error:
         return f"Kimi connection failed: {error}" 


if __name__ == "__main__":

    manager = ModelManager()

    print("Available Ollama models:")

    for model in manager.get_available_models():
        print("-", model)

    print("\nCurrent provider:", manager.current_provider)
    print("Current model:", manager.current_model)
