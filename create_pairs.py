import json
import os

raw_folder = "raw_texts"
output_file = "train.jsonl"

os.makedirs(raw_folder, exist_ok=True)

def make_simple_answer(text):
    # Replace this later with better rewriting logic
    # For now it just truncates – you will improve it
    return (
        "This is a simple explanation written at a 5th-grade reading level. "
        + text[:400].replace("\n", " ") + "..."
    )

with open(output_file, "w", encoding="utf-8") as out:
    files = [f for f in os.listdir(raw_folder) if f.endswith(".txt")]
    
    if not files:
        print(f"No .txt files found in '{raw_folder}'. Add some raw legal texts first.")
    else:
        for filename in files:
            path = os.path.join(raw_folder, filename)
            with open(path, "r", encoding="utf-8") as f:
                raw = f.read().strip()

            if not raw:
                continue

            pair = {
                "messages": [
                    {
                        "role": "user",
                        "content": "Explain this legal text in very simple words a 5th grader can understand:\n\n" + raw[:1500]
                    },
                    {
                        "role": "assistant",
                        "content": make_simple_answer(raw)
                    }
                ]
            }
            out.write(json.dumps(pair, ensure_ascii=False) + "\n")

        print(f"Created {output_file} from {len(files)} files.")