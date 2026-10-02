# Path content lives in Eliot100/MyRoad-content

This directory is the **checkout / submodule target** for learning-path JSON.
The platform no longer owns path content in-tree as the source of truth.

## How the loader finds content

`myroad_core.content.loader.default_content_dir()` checks, in order:

1. `CONTENT_DIR` env var
2. This directory (`packages/core/content`) — populate via submodule or copy
3. Sibling `../MyRoad-content` (clone next to the MyRoad repo)
4. Repo-root `content/`

## Setup

```bash
# Option A: CONTENT_DIR
git clone https://github.com/Eliot100/MyRoad-content.git ../MyRoad-content
export CONTENT_DIR="$(cd ../MyRoad-content && pwd)"

# Option B: submodule (if configured)
git submodule update --init --recursive

# Option C: copy for local/CI vendor
cp -R ../MyRoad-content/grade3 packages/core/content/
```

Grade-3 demos: 10 JSON files under `grade3/`.
