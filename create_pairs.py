import json
import os

# Put your raw legal text files in a folder called "raw_texts"
raw_folder = "raw_texts"
output_file = "train.jsonl"

def make_simple_answer(text):
    # This is a placeholder. You should improve this or do it by hand at first.
    # Later you can make this smarter.
    return "This is a simple explanation written at a 5th-grade reading level. " + text[:300] + "..."

with open(output_file, "w", encoding="utf-8") as out:
    for filename in os.listdir(raw_folder):
        if filename.endswith(".txt"):
            with open(os.path.join(raw_folder, filename), "r", encoding="utf-8") as f:
                raw = f.read()

            # Example pair – rewrite the assistant part in real 5th-grade English
            pair = {
                "messages": [
                    {"role": "user", "content": f"Explain this legal text in simple words:\n\n{raw[:500]}"},
                    {"role": "assistant", "content": make_simple_answer(raw)}
                ]
            }
            out.write(json.dumps(pair, ensure_ascii=False) + "\n")

print("Finished creating train.jsonl")