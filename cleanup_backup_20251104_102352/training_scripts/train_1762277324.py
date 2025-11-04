#!/usr/bin/env python3
"""
Auto-generated Unsloth training script.
Generated at: 2025-11-04 09:28:44
"""

import json
import torch
from unsloth import FastLanguageModel
from trl import SFTTrainer
from transformers import TrainingArguments
from datasets import load_dataset

# Configuration
BASE_MODEL = "google/gemma-3-12b-it"
OUTPUT_DIR = "data/fine_tuned_models/test"
DATASET_PATH = "data/training_datasets/test.jsonl"
MAX_SEQ_LENGTH = 2048
LOAD_IN_4BIT = false

# LoRA configuration
LORA_R = 16
LORA_ALPHA = 32
LORA_DROPOUT = 0.05

# Training configuration
NUM_EPOCHS = 1
BATCH_SIZE = 2
GRADIENT_ACCUMULATION_STEPS = 4
LEARNING_RATE = 0.0002
WARMUP_STEPS = 10

print("🚀 Starting Unsloth fine-tuning...")
print(f"Base model: {BASE_MODEL}")
print(f"Dataset: {DATASET_PATH}")
print(f"Output: {OUTPUT_DIR}")

# Load model with Unsloth
print("\n📦 Loading model...")
model, tokenizer = FastLanguageModel.from_pretrained(
    model_name=BASE_MODEL,
    max_seq_length=MAX_SEQ_LENGTH,
    dtype=None,  # Auto-detect
    load_in_4bit=LOAD_IN_4BIT,
)

# Add LoRA adapters
print("\n🔧 Adding LoRA adapters...")
model = FastLanguageModel.get_peft_model(
    model,
    r=LORA_R,
    target_modules=["q_proj", "k_proj", "v_proj", "o_proj",
                    "gate_proj", "up_proj", "down_proj"],
    lora_alpha=LORA_ALPHA,
    lora_dropout=LORA_DROPOUT,
    bias="none",
    use_gradient_checkpointing=True,
    random_state=42,
)

# Load dataset
print("\n📊 Loading dataset...")
dataset = load_dataset("json", data_files=str(DATASET_PATH), split="train")
print(f"Dataset size: {len(dataset)} samples")

# Format dataset for ChatML
def formatting_func(examples):
    texts = []
    for messages in examples["messages"]:
        text = tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=False
        )
        texts.append(text)
    return {"text": texts}

dataset = dataset.map(formatting_func, batched=True)

# Training arguments
print("\n⚙️  Setting up training...")
training_args = TrainingArguments(
    output_dir=OUTPUT_DIR,
    num_train_epochs=NUM_EPOCHS,
    per_device_train_batch_size=BATCH_SIZE,
    gradient_accumulation_steps=GRADIENT_ACCUMULATION_STEPS,
    learning_rate=LEARNING_RATE,
    warmup_steps=WARMUP_STEPS,
    logging_steps=10,
    save_steps=100,
    eval_steps=100,
    fp16=true,
    bf16=false,
    optim="adamw_8bit",
    weight_decay=0.01,
    max_grad_norm=1.0,
    seed=42,
    report_to="none",  # Disable wandb/tensorboard
)

# Create trainer
trainer = SFTTrainer(
    model=model,
    tokenizer=tokenizer,
    train_dataset=dataset,
    dataset_text_field="text",
    max_seq_length=MAX_SEQ_LENGTH,
    args=training_args,
)

# Train
print("\n🏋️  Training started...")
print("=" * 60)
trainer.train()
print("=" * 60)
print("\n✅ Training completed!")

# Save model
print(f"\n💾 Saving model to {OUTPUT_DIR}...")
model.save_pretrained(OUTPUT_DIR)
tokenizer.save_pretrained(OUTPUT_DIR)

print("\n🎉 Fine-tuning complete!")
print(f"Model saved to: {OUTPUT_DIR}")
