import json

# ============================================
# SMOKE TEST - Fine-tune the 5th-grade style here
# ============================================

# Paste a short real legal text for testing
raw_text = """
The court held that the defendant violated the plaintiff's civil rights under 42 U.S.C. § 1983 by acting under color of state law and depriving the plaintiff of due process.
"""

def make_simple_answer(text):
    """
    This is the heart of the smoke test.
    Edit this function until the answers sound like clear 5th-grade English.
    """
    return (
        "The court said the person broke the other person's rights. "
        "They used power from a government job to do it. "
        "That is not allowed under a law called Section 1983. "
        "The person who was hurt can take them to court."
    )

pair = {
    "messages": [
        {
            "role": "user",
            "content": "Explain this legal text in very simple words a 5th grader can understand:\n\n" + raw_text.strip()
        },
        {
            "role": "assistant",
            "content": make_simple_answer(raw_text)
        }
    ]
}

with open("smoke_test_pair.jsonl", "w", encoding="utf-8") as f:
    f.write(json.dumps(pair, ensure_ascii=False, indent=2))

print("Smoke test pair created → smoke_test_pair.jsonl")
print("Open that file and check if the answer sounds simple enough.")
print("Edit the make_simple_answer function and run again until you like it.")