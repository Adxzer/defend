# pydefend

Python SDK for Defend guardrails.

- Install: `pip install pydefend`
- Import: `from defend import Client`
- Python: `>=3.12`

## Quick start

```python
from defend import Client

client = Client(api_key="dev", base_url="http://localhost:8000")
result = client.input("Hello")
print(result.action)
```

## Repository and docs

Source, API docs, and full setup guide:

https://github.com/Adxzer/defend
