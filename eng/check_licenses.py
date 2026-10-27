import json
from pathlib import Path
import sys


def check(document):
    for dep in document["dependencies"]:
        assert dep["license"] in document["allowedLicenses"], dep["name"]
        if dep["name"] == "UnityDoorstop":
            assert dep["role"] == "control-only"


if __name__ == "__main__":
    lock_path = Path(__file__).resolve().parent / "dependencies.lock.json"
    document = json.loads(lock_path.read_text(encoding="utf-8"))
    check(document)
    print("License policy passed for all locked dependencies.")
    sys.exit(0)
