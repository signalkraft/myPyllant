#!/usr/bin/env python3
import re
from pathlib import Path

if __name__ == "__main__":
    readme = Path(__file__).resolve().parents[3] / "README.md"
    sample = Path(__file__).resolve().parents[1] / "sample.py"
    mypyllant_component = Path(__file__).resolve().parents[4] / "mypyllant-component"

    # README
    new_readme_content = f"""## Using the API in Python

```python
{sample.read_text()}
```
"""
    new_readme = re.sub(
        r"## Using the API in Python(.+?)```\n",
        new_readme_content,
        readme.read_text(),
        flags=re.DOTALL,
    )
    if readme.read_text() != new_readme:
        readme.write_text(
            re.sub(
                r"## Using the API in Python(.+?)```\n",
                new_readme_content,
                readme.read_text(),
                flags=re.DOTALL,
            )
        )
        print("README.md was updated with latest sample.py")

    # Docs
    if mypyllant_component.exists():
        docs = (
            Path(__file__).resolve().parents[4]
            / "mypyllant-component/docs/docs/2-library.md"
        )
        new_docs_content = f"""## Using the API in Python

```python
{sample.read_text()}
```
"""
        new_docs = re.sub(
            r"## Using the API in Python(.+?)```\n",
            new_docs_content,
            docs.read_text(),
            flags=re.DOTALL,
        )
        if docs.read_text() != new_docs:
            docs.write_text(
                re.sub(
                    r"## Using the API in Python(.+?)```\n",
                    new_docs_content,
                    docs.read_text(),
                    flags=re.DOTALL,
                )
            )
            print("docs/2-library.md was updated with latest sample.py")
