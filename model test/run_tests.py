
import json
import time
from pathlib import Path
from datetime import datetime

from model_manager import ModelManager
from research_tasks import RESEARCH_TASKS


def run_model_tests():

    manager = ModelManager()

    model_name = manager.current_model

    print("\nKAIRO MODEL TESTING LAB")
    print("=======================")
    print(f"Testing model: {model_name}")

    results = []

    output_folder = Path(__file__).resolve().parent / "results"
    output_folder.mkdir(exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    output_file = output_folder / f"{model_name.replace(':', '_')}_{timestamp}.json"

    for index, task in enumerate(RESEARCH_TASKS, start=1):

        print(f"\nTask {index}/{len(RESEARCH_TASKS)}")
        print(f"Assignment: {task['title']}")

        start_time = time.time()

        response = manager.generate_response(task["prompt"])

        duration = round(time.time() - start_time, 2)

        result = {
            "model": model_name,
            "task_id": task["id"],
            "category": task["category"],
            "title": task["title"],
            "response": response,
            "duration_seconds": duration,
            "timestamp": datetime.now().isoformat()
        }

        results.append(result)

        # Save after every assignment
        with open(output_file, "w", encoding="utf-8") as file:
            json.dump(results, file, indent=4, ensure_ascii=False)

        print(f"Completed in {duration} seconds")
        print(f"Saved: {output_file}")

    print("\n=======================")
    print("ALL TESTS COMPLETED")
    print(f"Results saved to: {output_file}")


if __name__ == "__main__":
    run_model_tests()
