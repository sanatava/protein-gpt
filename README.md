# Structural Biology MCP Agent

An AI agent for structural biology that uses [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) to search, analyze, modify, and visualize protein structures from the [RCSB Protein Data Bank](https://www.rcsb.org/).

## Architecture

```
User (browser)
    |
Streamlit Chat UI (protein_chat_mcp.py)
    |
Claude AI (decides which tools to call)
    |
MCP Client (standard protocol)
    |
PDB MCP Server (pdb_mcp_server.py) ── 11 tools
    |
RCSB PDB APIs
```

**Why MCP?** MCP is a standard protocol for AI-tool communication. Instead of hardcoding tools inside the app, the MCP server exposes tools that *any* MCP-compatible AI client can discover and use automatically — Claude Code, Cursor, or this custom Streamlit app.

## 11 Tools

| # | Tool | Description |
|---|------|-------------|
| 1 | `search_structures` | Search PDB by keyword, filter by method/resolution |
| 2 | `get_structure_info` | Get detailed metadata for a PDB ID |
| 3 | `download_structure` | Download PDB coordinate files |
| 4 | `search_by_uniprot` | Find structures linked to a UniProt accession |
| 5 | `get_structure_quality` | Resolution, R-factors, Ramachandran validation |
| 6 | `replace_metal` | Swap metals in HETATM records (e.g., Co → Zn) |
| 7 | `mutate_residue` | Mutate amino acids (e.g., HIS93 → SER) |
| 8 | `remove_hetatm` | Remove specific ligands/heteroatoms |
| 9 | `remove_chain` | Remove a chain from a multi-chain structure |
| 10 | `list_hetatm` | List all ligands/heteroatoms in a structure |
| 11 | `get_modified_structure` | Retrieve a modified PDB file |

## Demo

Ask the chat app:
> "Download 1YOG, replace cobalt with zinc, and show me the structure"

Claude automatically chains 3 MCP tool calls:
1. `download_structure("1YOG")` → fetches PDB file
2. `replace_metal("1YOG", "CO", "ZN")` → swaps Co→Zn in HETATM records
3. `show_structure_3d("1YOG_ZN")` → renders interactive 3D viewer

## Quick Start

### 1. Install dependencies

```bash
pip install "mcp[cli]" requests streamlit anthropic py3Dmol
```

### 2. Run the chat app

```bash
cd protein_chat
streamlit run protein_chat_mcp.py
```

Enter your Anthropic API key in the sidebar. Start chatting about protein structures.

### 3. Or use with Claude Code directly

```bash
claude mcp add pdb-server python /path/to/pdb_mcp_server.py
```

Then ask Claude Code: "Search PDB for cryoEM spike protein structures under 3A resolution"

## Project Structure

```
structural-biology-mcp/
  pdb_mcp_server.py                # MCP server (11 tools)
  protein_chat/
    protein_chat_mcp.py            # Streamlit chat app (MCP client)
    .streamlit/config.toml         # Dark theme config
    requirements.txt               # Python dependencies
  PDB_MCP_Server_Tutorial.ipynb    # Tutorial notebook
  requirements.txt                 # Server dependencies
```

## APIs Used

- [RCSB PDB Data API](https://data.rcsb.org/) - Structure metadata
- [RCSB PDB Search API](https://search.rcsb.org/) - Full-text and attribute search
- [RCSB PDB Files](https://files.rcsb.org/) - Coordinate file downloads

## Requirements

- Python 3.10+
- `mcp[cli]` >= 1.0
- `anthropic` >= 0.40.0
- `streamlit` >= 1.37.0
- `py3Dmol`
- `requests`

## License

MIT
