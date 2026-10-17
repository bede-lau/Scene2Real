"""Smoke-test every sponsor connection. Run: uv run check_connections.py"""
import os

import boto3
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()


def check_vast_s3():
    if not os.getenv("VAST_S3_ENDPOINT"):
        return "SKIP  VAST_S3_ENDPOINT not set"
    s3 = boto3.client(
        "s3",
        endpoint_url=os.getenv("VAST_S3_ENDPOINT"),
        aws_access_key_id=os.getenv("VAST_S3_ACCESS_KEY"),
        aws_secret_access_key=os.getenv("VAST_S3_SECRET_KEY"),
    )
    buckets = [b["Name"] for b in s3.list_buckets()["Buckets"]]
    return f"OK    buckets: {', '.join(buckets) or '(none)'}"


def check_openai_compatible(base_env, key_env):
    if not os.getenv(base_env):
        return f"SKIP  {base_env} not set"
    client = OpenAI(base_url=os.getenv(base_env), api_key=os.getenv(key_env) or "none")
    models = [m.id for m in client.models.list().data]
    return f"OK    {len(models)} models: {', '.join(models[:6])}"


checks = [
    ("VAST S3", check_vast_s3),
    ("Cosmos/VSS", lambda: check_openai_compatible("COSMOS_BASE_URL", "COSMOS_API_KEY")),
    ("W&B Inference", lambda: check_openai_compatible("WANDB_BASE_URL", "WANDB_API_KEY")),
]
for name, fn in checks:
    try:
        print(f"{name:14} {fn()}")
    except Exception as e:
        print(f"{name:14} FAIL  {e}")
