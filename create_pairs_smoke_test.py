import json

# ============================================
# SMOKE TEST VERSION
# Use this to fine-tune how the simple English answers look
# ============================================

# 1. Put a short piece of real legal text here for testing
raw_text = """
The court held that the defendant violated the plaintiff's civil rights under 42 U.S.C. § 1983 by acting under color of state law and depriving the plaintiff of due process.
"""

# 2. This is the prompt / instruction that controls the simple English style
#    Change this part until you like the results
def make_simple_answer(text):
    # You will improve this function
    simple = f"""Explain the following legal text in very simple 5th-grade English.
Use short sentences and easy words. Do not use legal jargon.

Legal text:
{text}

Simple explanation:"""

    # For the smoke test we just pretend / write a sample answer.
    # Later you can connect a real model or rewrite by hand.
    return "The court said the person broke the other person's rights. They used a government job to do it. This is not allowed. The person who was hurt can take them to court."


# 3. Create one test pair
pair = {
    "messages": [
        {
            "role": "user",
            "content": "Explain this in simple words:\n\n" + raw_text.strip()
        },
        {
            "role": "assistant",
            "content": make_simple_answer(raw_text)
        }
    ]
}

# 4. Save it so you can look at it
with open("smoke_test_pair.jsonl", "w", encoding="utf-8") as f:
    f.write(json.dumps(pair, ensure_ascii=False, indent=2))

print("Smoke test pair created!")
print("Open the file 'smoke_test_pair.jsonl' and read the answer.")
print("Change the make_simple_answer function until you like how it sounds.")



##How to use this smoke test

#Copy the code into a file called create_pairs_smoke_test.py
#Paste a real short piece of legal text into the raw_text = """ ... """ part
#Run it:Bashpython create_pairs_smoke_test.py
#Open smoke_test_pair.jsonl and read the answer
#Edit the make_simple_answer function (or the prompt inside it)
#Run it again
#Repeat until the simple English sounds the way you want