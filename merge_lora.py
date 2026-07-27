from unsloth import FastLanguageModel

model, tokenizer = FastLanguageModel.from_pretrained(
    model_name = "melilo-7b-qlora",
    max_seq_length = 4096,
    dtype = None,
    load_in_4bit = True,
)

model = FastLanguageModel.merge_and_unload(model)
model.save_pretrained("melilo-7b-merged")
tokenizer.save_pretrained("melilo-7b-merged")
print("Merged model saved!")