#!/usr/bin/env python3
import os
from pathlib import Path
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv(Path(__file__).parent.parent / "infra" / ".env")

client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
models = sorted(m.id for m in client.models.list())
for m in models:
    print(m)
