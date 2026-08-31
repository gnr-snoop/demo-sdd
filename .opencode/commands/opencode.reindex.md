---
description: Refresh the codebase-memory knowledge graph index so architecture analysis uses up-to-date data.
---

## Goal

Ensure the codebase-memory knowledge graph is fresh before `@speckit-plan` runs its architecture analysis. Without a fresh index, `get_architecture`, `search_graph`, and `trace_path` may return stale or incomplete results.

## Execution

1. Check if codebase-memory MCP server is available (the `codebase-memory-mcp_*` tools are accessible).

2. **If codebase-memory is NOT available**:
   - Report: "codebase-memory MCP server not available, skipping reindex"
   - Exit gracefully — the plan command will still work, just without graph-augmented analysis

3. **If codebase-memory IS available**:
   - Run `codebase-memory-mcp_list_projects` to check if this project is already indexed
   - Derive the project name from the repo directory name dynamically (basename of the repo root)

   - **If project is NOT indexed** (not in list):
     - Run `codebase-memory-mcp_index_repository` with:
       - `repo_path`: the current repository root path
       - `mode`: `"moderate"` (filtered files + similarity/semantic edges — good balance for planning)
       - `persistence`: `false` (no artifact write needed for local dev)
     - Report: "Indexed project for the first time"

   - **If project IS indexed**:
     - Run `codebase-memory-mcp_index_status` to check current status
     - Run `codebase-memory-mcp_detect_changes` with `depth: 2` to see if there are meaningful changes since last index
     - **If changes detected**:
       - Run `codebase-memory-mcp_index_repository` with:
         - `repo_path`: the current repository root path
         - `mode`: `"fast"` (filtered files, no similarity/semantic — faster for re-index)
         - `persistence`: `false`
       - Report: "Re-indexed project (N changes detected)"
     - **If no changes detected**:
       - Report: "Index is already fresh, skipping reindex"
       - Exit without re-indexing

4. After indexing (or confirming freshness), run `codebase-memory-mcp_get_architecture` with `aspects: ["all"]` to verify the graph is queryable. Report a brief summary:
   - Number of nodes
   - Number of edges
   - Top-level packages/clusters detected

## Notes

- This hook runs before `@speckit-plan` starts its outline
- It is optional (`optional: true`) — if it fails, planning continues anyway
- Uses `mode: "moderate"` for first index (richer graph) and `mode: "fast"` for re-indexes (speed)
- The project name may vary — use the repo directory name as the project identifier
