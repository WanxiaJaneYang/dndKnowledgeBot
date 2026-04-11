"""
PostToolUse hook: validate JSON syntax after Write|Edit on schemas/ or examples/ files.
Outputs a systemMessage if the file has a JSON syntax error.
"""
import json
import os
import sys


def main():
    try:
        data = json.load(sys.stdin)
        fp = data.get("tool_input", {}).get("file_path", "")
        if not fp.endswith(".json"):
            return
        fp_unix = fp.replace("\\", "/")
        if not any(seg in fp_unix for seg in ["schemas/", "examples/"]):
            return
        with open(fp) as f:
            json.load(f)
    except json.JSONDecodeError as e:
        name = os.path.basename(fp) if fp else "file"
        print(json.dumps({"systemMessage": f"JSON syntax error in {name}: {e}"}))
    except Exception:
        pass


if __name__ == "__main__":
    main()
