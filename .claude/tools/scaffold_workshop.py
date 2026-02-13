"""Scaffold boilerplate files for new AgentCore workshops.

Usage:
    uv run python .claude/tools/scaffold_workshop.py 05_evaluation \
        --title "AgentCore Evaluation" \
        --description "Quality assurance with built-in and custom evaluators"
"""

import argparse
import sys
from pathlib import Path

FOUNDATION_MAX = 5  # 01-05 = Foundation, 06-09 = Extension


def get_category(dir_name: str) -> str:
    """Determine Foundation or Extension from the directory number prefix."""
    num = int(dir_name.split("_")[0])
    return "Foundation" if num <= FOUNDATION_MAX else "Extension"


def get_prev_next(dir_name: str, all_dirs: list[str]) -> tuple[str | None, str | None]:
    """Find previous and next workshop directories."""
    try:
        idx = all_dirs.index(dir_name)
    except ValueError:
        return None, None
    prev_dir = all_dirs[idx - 1] if idx > 0 else None
    next_dir = all_dirs[idx + 1] if idx < len(all_dirs) - 1 else None
    return prev_dir, next_dir


def discover_workshops(base: Path) -> list[str]:
    """Return sorted list of workshop directory names."""
    dirs = sorted(
        d.name for d in base.iterdir() if d.is_dir() and d.name[:2].isdigit()
    )
    return dirs


def readme_en(title: str, description: str, dir_name: str, next_dir: str | None) -> str:
    """Generate README.md content."""
    feature = title.replace("AgentCore ", "")
    next_line = (
        f"Continue with [{next_dir}](../{next_dir}/README.md) "
        f"to explore the next workshop."
        if next_dir
        else "Check back for more workshops coming soon."
    )

    return f"""\
# {title} Integration

[English](README.md) / [日本語](README_ja.md)

{description}

## Process Overview

```mermaid
sequenceDiagram
    participant User as User Input
    participant Agent as Agent
    participant AC as AgentCore {feature}

    User->>Agent: TODO: describe interaction
    Agent->>AC: TODO: describe request
    AC-->>Agent: TODO: describe response
    Agent-->>User: TODO: describe output
```

## Prerequisites

1. **AWS credentials** - With Bedrock AgentCore access permissions
2. **Python 3.12+** - Required for async/await support
3. **Dependencies** - Installed via `uv` (see pyproject.toml)
4. **Prior workshops** - TODO: list prerequisite workshops

## How to use

### File Structure

```
{dir_name}/
├── README.md                           # This documentation
├── README_ja.md                        # Japanese documentation
├── test_{feature.lower().replace(" ", "_")}.py  # TODO: main test script
└── clean_resources.py                  # Resource cleanup
```

### Step 1: TODO: First Action

```bash
cd {dir_name}
uv run python test_{feature.lower().replace(" ", "_")}.py
```

TODO: Describe what this step does and what output to expect.

### Step 2: TODO: Second Action

```bash
cd {dir_name}
# TODO: add command
```

TODO: Describe the second step.

## Key Implementation Pattern

### TODO: Setup Pattern

```python
# TODO: Add setup code example
pass
```

### TODO: Core Feature Pattern

```python
# TODO: Add core feature code example
pass
```

### TODO: Resource Management Pattern

```python
# TODO: Add resource management code example
pass
```

## Usage Example

```python
# TODO: Add complete working example
pass
```

## {feature} Benefits

- TODO: Benefit 1
- TODO: Benefit 2
- TODO: Benefit 3
- TODO: Benefit 4

## References

- [AgentCore {feature} Developer Guide](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/)
- [Strands Agents Documentation](https://github.com/aws-samples/strands-agents)

---

**Next Steps**: {next_line}
"""


def readme_ja(
    title: str, description: str, dir_name: str, next_dir: str | None
) -> str:
    """Generate README_ja.md content."""
    feature = title.replace("AgentCore ", "")
    next_line = (
        f"[{next_dir}](../{next_dir}/README.md) に進んで、"
        f"次のワークショップを体験しましょう。"
        if next_dir
        else "今後のワークショップにご期待ください。"
    )

    return f"""\
# {title}統合

[English](README.md) / [日本語](README_ja.md)

{description}

## プロセス概要

```mermaid
sequenceDiagram
    participant User as ユーザー入力
    participant Agent as エージェント
    participant AC as AgentCore {feature}

    User->>Agent: TODO: インタラクションの説明
    Agent->>AC: TODO: リクエストの説明
    AC-->>Agent: TODO: レスポンスの説明
    Agent-->>User: TODO: 出力の説明
```

## 前提条件

1. **AWS認証情報** - Bedrock AgentCoreアクセス権限付き
2. **Python 3.12+** - async/awaitサポートに必要
3. **依存関係** - `uv`経由でインストール（pyproject.toml参照）
4. **前提ワークショップ** - TODO: 前提となるワークショップを記載

## 使用方法

### ファイル構成

```
{dir_name}/
├── README.md                           # 英語ドキュメント
├── README_ja.md                        # このドキュメント
├── test_{feature.lower().replace(" ", "_")}.py  # TODO: メインテストスクリプト
└── clean_resources.py                  # リソースクリーンアップ
```

### ステップ1: TODO: 最初のアクション

```bash
cd {dir_name}
uv run python test_{feature.lower().replace(" ", "_")}.py
```

TODO: このステップの内容と期待される出力を説明します。

### ステップ2: TODO: 2番目のアクション

```bash
cd {dir_name}
# TODO: コマンドを追加
```

TODO: 2番目のステップを説明します。

## 主要な実装パターン

### TODO: セットアップパターン

```python
# TODO: セットアップコードの例を追加
pass
```

### TODO: コア機能パターン

```python
# TODO: コア機能コードの例を追加
pass
```

### TODO: リソース管理パターン

```python
# TODO: リソース管理コードの例を追加
pass
```

## 使用例

```python
# TODO: 完全な動作例を追加
pass
```

## {feature}の利点

- TODO: 利点1
- TODO: 利点2
- TODO: 利点3
- TODO: 利点4

## 参考資料

- [AgentCore {feature}開発者ガイド](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/)
- [Strands Agentsドキュメント](https://github.com/aws-samples/strands-agents)

---

**次のステップ**: {next_line}
"""


def clean_resources_py(title: str, dir_name: str) -> str:
    """Generate clean_resources.py content."""
    feature = title.replace("AgentCore ", "")
    snake = feature.lower().replace(" ", "_")

    return f"""\
import json
import os
from pathlib import Path

import boto3


def clean_resources():
    \"\"\"Clean up all resources created by {dir_name} ({feature}).\"\"\"
    # TODO: Define the config file name if this workshop generates one
    # config_file = Path("{snake}_config.json")

    region = boto3.Session().region_name
    client = boto3.client("bedrock-agentcore-control", region_name=region)

    # TODO: Read config and delete resources in dependency order
    # Example:
    #   with config_file.open("r", encoding="utf-8") as f:
    #       config = json.load(f)
    #   client.delete_...(...)

    print("TODO: implement resource cleanup for {feature}")

    # TODO: Remove generated config files
    # os.remove(config_file)


if __name__ == "__main__":
    clean_resources()
"""


def scaffold(
    base: Path, dir_name: str, title: str, description: str, *, force: bool = False
) -> list[str]:
    """Generate scaffold files for a workshop. Returns list of created files."""
    workshop_dir = base / dir_name
    if not workshop_dir.is_dir():
        print(f"Error: directory {workshop_dir} does not exist", file=sys.stderr)
        sys.exit(1)

    all_dirs = discover_workshops(base)
    _prev, next_dir = get_prev_next(dir_name, all_dirs)
    category = get_category(dir_name)

    files = {
        "README.md": readme_en(title, description, dir_name, next_dir),
        "README_ja.md": readme_ja(title, description, dir_name, next_dir),
        "clean_resources.py": clean_resources_py(title, dir_name),
    }

    created = []
    for filename, content in files.items():
        path = workshop_dir / filename
        if path.exists() and not force:
            print(f"  SKIP {path.relative_to(base)} (already exists)")
            continue
        path.write_text(content, encoding="utf-8")
        created.append(str(path.relative_to(base)))
        print(f"  CREATE {path.relative_to(base)}")

    print(f"\nCategory: {category} (workshops 01-05=Foundation, 06-09=Extension)")
    return created


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Scaffold boilerplate files for a new AgentCore workshop"
    )
    parser.add_argument(
        "dir_name",
        help="Workshop directory name (e.g. 05_evaluation)",
    )
    parser.add_argument(
        "--title",
        required=True,
        help='Workshop title (e.g. "AgentCore Evaluation")',
    )
    parser.add_argument(
        "--description",
        required=True,
        help="One-line description of the workshop",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing files",
    )
    args = parser.parse_args()

    base = Path(__file__).resolve().parent.parent
    print(f"Scaffolding {args.dir_name}...")
    scaffold(base, args.dir_name, args.title, args.description, force=args.force)
    print("Done.")


if __name__ == "__main__":
    main()
