
import json
from pathlib import Path


SCORING_CATEGORIES = [
    "accuracy",
    "reasoning",
    "depth",
    "completeness",
    "clarity"
]


def calculate_score(scores):
    return sum(scores.values())


def evaluate_results(results):

    for result in results:

        print("\n" + "=" * 50)
        print("TASK:", result["title"])
        print("=" * 50)

        print("\nMODEL RESPONSE:\n")
        print(result["response"])

        print("\nScore this answer from 0 to 10.")

        scores = {}

        for category in SCORING_CATEGORIES:

            while True:
                try:
                    score = int(input(f"{category.title()} (0-10): "))

                    if 0 <= score <= 10:
                        scores[category] = score
                        break

                    print("Enter a number between 0 and 10.")

                except ValueError:
                    print("Please enter a valid number.")

        result["scores"] = scores
        result["total_score"] = calculate_score(scores)

        print(f"\nTotal score: {result['total_score']}/50")

    return results


def main():

    results_folder = Path(__file__).resolve().parent / "results"

    files = sorted(
        results_folder.glob("*.json"),
        key=lambda file: file.stat().st_mtime,
        reverse=True
    )

    if not files:
        print("No model test results found.")
        return

    print("Available result:", files[0].name)

    with open(files[0], "r", encoding="utf-8") as file:
        results = json.load(file)

    results = evaluate_results(results)

    output_file = files[0].with_name(
        files[0].stem + "_evaluated.json"
    )

    with open(output_file, "w", encoding="utf-8") as file:
        json.dump(results, file, indent=4, ensure_ascii=False)

    print("\nEVALUATION COMPLETE")
    print("Saved to:", output_file)


if __name__ == "__main__":
    main()
