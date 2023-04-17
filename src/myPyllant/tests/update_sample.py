#!/usr/bin/env python3
import re
from pathlib import Path

if __name__ == "__main__":
    readme = Path(__file__).resolve().parents[3] / "README.md"
    sample = Path(__file__).resolve().parents[1] / "sample.py"
    new_content = f"""## Usage

```python
{sample.read_text()}
```
"""
    new_readme = re.sub(
        r"## Usage(.+?)```\n", new_content, readme.read_text(), flags=re.DOTALL
    )
    if readme.read_text() != new_readme:
        readme.write_text(
            re.sub(
                r"## Usage(.+?)```\n", new_content, readme.read_text(), flags=re.DOTALL
            )
        )
        print("README.md was updated with latest sample.py")
