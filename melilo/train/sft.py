"""Supervised fine-tuning entry point for the Melilo student model.

v0 scaffold: loads pair JSONL into a HF Dataset, formats as chat messages,
runs SFTTrainer on the configured student model. Wire up once we have pairs.
"""
from __future__ import annotations

from dataclasses import dataclass

from melilo.config import settings
from melilo.translate.prompts import SYSTEM_PROMPT, USER_TEMPLATE


@dataclass
class TrainConfig:
    pairs_path: str  # local path or s3://... resolved by the caller
    output_dir: str = "checkpoints/melilo-v0"
    epochs: int = 1
    learning_rate: float = 2e-5
    per_device_batch_size: int = 4
    gradient_accumulation_steps: int = 8
    max_seq_length: int = 4096


def format_example(record: dict) -> dict:
    """Turn a pair record into a chat-format SFT example."""
    return {
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": USER_TEMPLATE.format(source_text=record["source_text"]),
            },
            {"role": "assistant", "content": record["translation"]},
        ]
    }


def run(cfg: TrainConfig) -> None:
    # Imports kept local so the CLI stays import-light when only ingesting.
    from datasets import load_dataset
    from transformers import AutoModelForCausalLM, AutoTokenizer
    from trl import SFTConfig, SFTTrainer

    tokenizer = AutoTokenizer.from_pretrained(settings.student_model)
    model = AutoModelForCausalLM.from_pretrained(settings.student_model)

    ds = load_dataset("json", data_files=cfg.pairs_path, split="train")
    ds = ds.map(format_example, remove_columns=ds.column_names)

    sft_cfg = SFTConfig(
        output_dir=cfg.output_dir,
        num_train_epochs=cfg.epochs,
        learning_rate=cfg.learning_rate,
        per_device_train_batch_size=cfg.per_device_batch_size,
        gradient_accumulation_steps=cfg.gradient_accumulation_steps,
        max_seq_length=cfg.max_seq_length,
        bf16=True,
        logging_steps=10,
        save_strategy="epoch",
    )
    SFTTrainer(model=model, tokenizer=tokenizer, args=sft_cfg, train_dataset=ds).train()
