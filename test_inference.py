from unsloth import FastLanguageModel

model, tokenizer = FastLanguageModel.from_pretrained(
    model_name = "melilo-7b-qlora",
    max_seq_length = 4096,
    dtype = None,
    load_in_4bit = True,
)
FastLanguageModel.for_inference(model)

messages = [
    {"role": "user", "content": "Explain what a statute is in very simple words a 5th grader can understand."}
]

inputs = tokenizer.apply_chat_template(
    messages,
    tokenize = True,
    add_generation_prompt = True,
    return_tensors = "pt"
).to("cuda")

outputs = model.generate(
    input_ids = inputs,
    max_new_tokens = 256,
    temperature = 0.3,
    do_sample = True
)

print(tokenizer.decode(outputs[0], skip_special_tokens = True))