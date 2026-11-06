"""Check the real project Qdrant; never print the API key or use a substitute."""
import json
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

root = Path(__file__).resolve().parents[1]
key = next(line.split("=", 1)[1].strip() for line in (root / ".env").read_text().splitlines()
           if line.startswith("QDRANT_API_KEY="))
assert key
def get(path, credential=None):
    headers = {"api-key": credential} if credential else {}
    try:
        with urlopen(Request("http://127.0.0.1:6333" + path, headers=headers), timeout=5) as response:
            return response.status, response.read().decode()
    except HTTPError as error:
        return error.code, ""

ready, _ = get("/readyz", key)
authorized, body = get("/collections", key)
anonymous, _ = get("/collections")
incorrect, _ = get("/collections", "invalid-r05-check")
assert ready == authorized == 200
assert anonymous in (401, 403) and incorrect in (401, 403)
result = {"ready": ready, "authorized": authorized, "anonymous": anonymous, "wrong_key": incorrect,
          "collections": json.loads(body)["result"]["collections"]}
(root / "docs/checks/stage1b-1-qdrant.json").write_text(json.dumps(result, indent=2) + "\n")
print(json.dumps(result, indent=2))
