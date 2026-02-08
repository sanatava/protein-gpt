#!/usr/bin/env python3
"""
ProteinChat AI (MCP Edition) — 3-Panel Layout
Streamlit chat app that connects to the PDB MCP Server via Model Context Protocol.

Architecture:
    User → Streamlit UI → Claude API → MCP Client → PDB MCP Server → RCSB PDB API

Layout:
    LEFT: Upload + Chat History + Examples
    CENTER: Chat conversation
    RIGHT: 3D Viewer + Downloads + Modification Steps
"""

import os
import sys
import json
import asyncio
import time
import uuid
import tempfile
import requests
import streamlit as st
import anthropic
import py3Dmol
import streamlit.components.v1 as components
from mcp import ClientSession
from mcp.client.stdio import stdio_client, StdioServerParameters

# ============================================================
# Page Config & CSS
# ============================================================

st.set_page_config(
    page_title="ProteinChat AI (MCP)",
    page_icon="🧬",
    layout="wide",
    initial_sidebar_state="collapsed",
)

CUSTOM_CSS = """
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

    /* ── Global ── */
    .stApp {
        background: linear-gradient(160deg, #060b14 0%, #0b1528 35%, #0d1018 70%, #080d16 100%);
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    }
    .main .block-container {
        padding-top: 0.8rem;
        padding-left: 0.8rem;
        padding-right: 0.8rem;
        max-width: 100%;
    }
    /* Hide page scroll only on large screens */
    @media (min-height: 820px) {
        .stApp { overflow: hidden !important; }
        .stApp > div[data-testid="stAppViewContainer"] { overflow: hidden !important; }
        .stApp [data-testid="stMain"] { overflow: hidden !important; }
        .main .block-container { overflow: hidden !important; }
    }
    section[data-testid="stSidebar"] { display: none; }

    /* ── Custom scrollbar ── */
    ::-webkit-scrollbar { width: 5px; }
    ::-webkit-scrollbar-track { background: transparent; }
    ::-webkit-scrollbar-thumb { background: rgba(0, 212, 170, 0.2); border-radius: 10px; }
    ::-webkit-scrollbar-thumb:hover { background: rgba(0, 212, 170, 0.4); }

    /* ── New Chat button (top-left) ── */
    .new-chat-row {
        display: flex;
        justify-content: flex-start;
        margin-bottom: 0.3rem;
    }
    .new-chat-row .stButton button {
        background: linear-gradient(135deg, #00d4aa 0%, #00b894 100%) !important;
        border: none !important;
        color: #060b14 !important;
        font-size: 0.8rem !important;
        font-weight: 600 !important;
        padding: 7px 20px !important;
        border-radius: 8px !important;
        transition: all 0.25s ease !important;
        box-shadow: 0 2px 10px rgba(0, 212, 170, 0.2) !important;
        letter-spacing: 0.3px !important;
    }
    .new-chat-row .stButton button:hover {
        box-shadow: 0 4px 18px rgba(0, 212, 170, 0.35) !important;
        transform: translateY(-1px) !important;
    }

    /* ── App header ── */
    .app-header {
        text-align: center;
        padding: 1rem 0 0.8rem 0;
        margin-bottom: 0.8rem;
        position: relative;
    }
    .app-header::after {
        content: '';
        position: absolute;
        bottom: 0;
        left: 15%;
        right: 15%;
        height: 1px;
        background: linear-gradient(90deg, transparent, rgba(0, 212, 170, 0.5), rgba(0, 255, 136, 0.3), transparent);
    }
    .app-header h1 {
        background: linear-gradient(135deg, #00d4aa 0%, #00ff88 50%, #00d4aa 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
        font-size: 2rem;
        font-weight: 700;
        margin-bottom: 0.2rem;
        letter-spacing: -0.5px;
        text-shadow: none;
        filter: drop-shadow(0 0 20px rgba(0, 212, 170, 0.3));
    }
    .app-header p {
        color: rgba(160, 174, 192, 0.7);
        font-size: 0.78rem;
        margin: 0;
        letter-spacing: 1.5px;
        text-transform: uppercase;
        font-weight: 400;
    }

    /* ── Glass panel base ── */
    .glass-panel {
        background: rgba(12, 18, 35, 0.55);
        backdrop-filter: blur(16px);
        -webkit-backdrop-filter: blur(16px);
        border: 1px solid rgba(0, 212, 170, 0.08);
        border-radius: 16px;
        padding: 1rem;
    }

    /* ── Left panel (style the column itself) ── */
    [data-testid="stColumns"] > div:first-child > [data-testid="stVerticalBlockBorderWrapper"] > div {
        background: rgba(12, 18, 35, 0.55);
        backdrop-filter: blur(16px);
        -webkit-backdrop-filter: blur(16px);
        border: 1px solid rgba(0, 212, 170, 0.08);
        border-radius: 16px;
        padding: 0.8rem;
        min-height: min(580px, 70vh);
    }

    /* General button styling */
    .stButton > button {
        border-radius: 8px !important;
        transition: all 0.2s ease !important;
    }

    /* History buttons */
    .stButton > button[kind="secondary"] {
        background: rgba(20, 28, 50, 0.6) !important;
        border: 1px solid rgba(0, 212, 170, 0.1) !important;
        border-radius: 10px !important;
        color: rgba(200, 210, 220, 0.8) !important;
        font-size: 0.82rem !important;
        text-align: left !important;
        transition: all 0.2s ease !important;
    }
    .stButton > button[kind="secondary"]:hover {
        background: rgba(0, 212, 170, 0.08) !important;
        border-color: rgba(0, 212, 170, 0.25) !important;
        color: #fff !important;
    }

    /* Delete button (trash icon) */
    [data-testid="stColumns"] button[kind="secondary"]:has(> div > p:only-child) {
        padding: 4px 6px !important;
        min-height: 0 !important;
        font-size: 0.75rem !important;
        opacity: 0.4;
        background: transparent !important;
        border: none !important;
    }
    [data-testid="stColumns"] button[kind="secondary"]:has(> div > p:only-child):hover {
        opacity: 1;
        background: rgba(255, 80, 80, 0.12) !important;
    }

    /* Section headers */
    .section-header {
        color: rgba(0, 212, 170, 0.7);
        font-size: 0.7rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 1.5px;
        margin: 0.8rem 0 0.4rem 0.3rem;
    }

    /* Gradient divider */
    .gradient-divider {
        height: 1px;
        background: linear-gradient(90deg, transparent, rgba(0, 212, 170, 0.2), transparent);
        margin: 0.6rem 0;
        border: none;
    }

    /* ── Center panel chat input (text_input) ── */
    [data-testid="stBottom"] {
        display: none !important;
    }

    /* Chat message styling */
    [data-testid="stChatMessage"] {
        background: rgba(15, 22, 40, 0.4) !important;
        border: 1px solid rgba(255, 255, 255, 0.03) !important;
        border-radius: 12px !important;
        padding: 0.8rem 1rem !important;
        margin-bottom: 0.5rem !important;
    }

    /* Structure notice */
    .structure-notice {
        background: rgba(0, 212, 170, 0.08);
        border: 1px solid rgba(0, 212, 170, 0.2);
        padding: 6px 14px;
        border-radius: 20px;
        font-size: 0.75rem;
        color: #00d4aa;
        margin-top: 6px;
        display: inline-block;
    }

    /* ── Right panel (style the column itself) ── */
    [data-testid="stColumns"] > div:last-child > [data-testid="stVerticalBlockBorderWrapper"] > div {
        background: rgba(12, 18, 35, 0.55);
        backdrop-filter: blur(16px);
        -webkit-backdrop-filter: blur(16px);
        border: 1px solid rgba(0, 212, 170, 0.1);
        border-radius: 16px;
        padding: 0.8rem;
        box-shadow: 0 0 30px rgba(0, 212, 170, 0.05);
    }

    .viewer-container {
        border: 1px solid rgba(0, 212, 170, 0.15);
        border-radius: 12px;
        overflow: hidden;
        margin: 5px 0;
        box-shadow: 0 0 25px rgba(0, 212, 170, 0.08);
    }

    /* Selectbox styling */
    .stSelectbox > div > div {
        background: rgba(15, 22, 40, 0.6) !important;
        border: 1px solid rgba(0, 212, 170, 0.12) !important;
        border-radius: 8px !important;
        font-size: 0.8rem !important;
    }

    /* Download buttons */
    .stDownloadButton > button {
        background: linear-gradient(135deg, #00d4aa 0%, #00b894 100%) !important;
        color: #060b14 !important;
        font-weight: 600 !important;
        border: none !important;
        border-radius: 10px !important;
        transition: all 0.3s ease !important;
        box-shadow: 0 2px 12px rgba(0, 212, 170, 0.15) !important;
    }
    .stDownloadButton > button:hover {
        box-shadow: 0 4px 20px rgba(0, 212, 170, 0.3) !important;
        transform: translateY(-1px) !important;
    }

    /* Empty viewer placeholder */
    .viewer-empty {
        height: min(400px, 50vh);
        display: flex;
        align-items: center;
        justify-content: center;
        border: 1px dashed rgba(0, 212, 170, 0.15);
        border-radius: 14px;
        color: rgba(120, 140, 160, 0.5);
        text-align: center;
        padding: 20px;
        font-size: 0.85rem;
        line-height: 1.8;
        background: rgba(12, 18, 35, 0.3);
    }
    .viewer-empty .icon {
        font-size: 2.5rem;
        margin-bottom: 0.5rem;
        opacity: 0.4;
    }

    /* Modification step */
    .mod-step {
        display: flex;
        align-items: center;
        gap: 8px;
        padding: 4px 0;
        font-size: 0.78rem;
        color: rgba(200, 210, 220, 0.7);
    }
    .mod-step .dot {
        width: 6px;
        height: 6px;
        border-radius: 50%;
        background: rgba(0, 212, 170, 0.4);
        flex-shrink: 0;
    }
    .mod-step.current .dot {
        background: #00d4aa;
        box-shadow: 0 0 8px rgba(0, 212, 170, 0.5);
    }
    .mod-step.current { color: #00d4aa; font-weight: 500; }

    /* ── MCP badge ── */
    .mcp-badge {
        background: rgba(0, 212, 170, 0.06);
        border: 1px solid rgba(0, 212, 170, 0.2);
        border-radius: 20px;
        padding: 4px 14px;
        display: inline-block;
        color: rgba(0, 212, 170, 0.8);
        font-size: 0.72rem;
        letter-spacing: 0.5px;
    }

    /* ── Welcome wrapper (fills the container, pushes content to center) ── */
    .welcome-wrapper {
        display: flex;
        flex-direction: column;
        min-height: min(510px, 62vh);
    }
    .welcome-wrapper .welcome-content {
        flex: 1;
        display: flex;
        flex-direction: column;
        justify-content: center;
        align-items: center;
        text-align: center;
        color: rgba(200, 210, 220, 0.7);
        padding: 1.5rem;
    }

    /* ── Chat text input (always in center column) ── */
    .stTextInput > div > div {
        background: rgba(12, 18, 35, 0.7) !important;
        border: 1px solid rgba(0, 212, 170, 0.18) !important;
        border-radius: 24px !important;
        padding: 4px 16px !important;
    }
    .stTextInput input {
        font-size: 0.85rem !important;
        color: #fafafa !important;
        padding: 8px 4px !important;
    }
    .stTextInput input::placeholder {
        color: rgba(160, 174, 192, 0.4) !important;
    }
    .stTextInput input:focus {
        border-color: rgba(0, 212, 170, 0.4) !important;
        box-shadow: 0 0 16px rgba(0, 212, 170, 0.12) !important;
    }

    /* ── Welcome box (empty chat) ── */
    .welcome-box {
        text-align: center;
        padding: 0;
        color: rgba(200, 210, 220, 0.7);
    }
    .welcome-icon {
        font-size: 3rem;
        margin-bottom: 0.8rem;
        opacity: 0.5;
    }
    .welcome-title {
        font-size: 1.3rem;
        font-weight: 600;
        color: rgba(255, 255, 255, 0.85);
        margin-bottom: 0.3rem;
    }
    .welcome-sub {
        font-size: 0.85rem;
        color: rgba(160, 174, 192, 0.6);
        margin-bottom: 1.5rem;
    }
    .welcome-examples {
        display: grid;
        grid-template-columns: 1fr 1fr 1fr;
        gap: 8px;
        max-width: 480px;
        margin: 0 auto;
    }
    .welcome-example {
        background: rgba(0, 212, 170, 0.06);
        border: 1px solid rgba(0, 212, 170, 0.12);
        border-radius: 10px;
        padding: 10px 12px;
        font-size: 0.75rem;
        color: rgba(200, 210, 220, 0.7);
        transition: all 0.2s ease;
    }
    .welcome-example:hover {
        background: rgba(0, 212, 170, 0.12);
        border-color: rgba(0, 212, 170, 0.25);
        color: #00d4aa;
    }

    /* ── Typing indicator (three dots) ── */
    .typing-indicator {
        display: flex;
        align-items: center;
        gap: 5px;
        padding: 8px 14px;
    }
    .typing-indicator span {
        width: 8px;
        height: 8px;
        border-radius: 50%;
        background: #00d4aa;
        animation: typing-bounce 1.4s ease-in-out infinite;
    }
    .typing-indicator span:nth-child(2) { animation-delay: 0.2s; }
    .typing-indicator span:nth-child(3) { animation-delay: 0.4s; }
    @keyframes typing-bounce {
        0%, 60%, 100% { opacity: 0.2; transform: translateY(0); }
        30% { opacity: 1; transform: translateY(-4px); }
    }

    /* ── Responsive adjustments ── */
    @media (max-height: 819px) {
        .app-header { padding: 0.4rem 0 0.4rem 0; margin-bottom: 0.4rem; }
        .app-header h1 { font-size: 1.5rem; }
        .app-header p { font-size: 0.65rem; }
        /* Shrink chat container on smaller screens */
        [data-testid="stVerticalBlockBorderWrapper"][data-testid-has-border] {
            max-height: 55vh !important;
        }
    }

    /* ── Developer contact ── */
    .dev-contact {
        padding-top: 0.3rem;
        text-align: center;
    }
    .dev-contact .dev-row {
        display: inline-flex;
        align-items: center;
        gap: 8px;
    }
    .dev-contact .dev-avatar {
        width: 34px;
        height: 34px;
        border-radius: 50%;
        background: linear-gradient(135deg, #0077b5, #00a0dc);
        display: flex;
        align-items: center;
        justify-content: center;
        flex-shrink: 0;
        transition: box-shadow 0.2s ease;
        overflow: hidden;
        text-decoration: none;
        color: #fff;
        font-size: 0.7rem;
        font-weight: 600;
    }
    .dev-contact .dev-avatar img {
        width: 100%;
        height: 100%;
        object-fit: cover;
    }
    .dev-contact .dev-avatar:hover {
        box-shadow: 0 0 12px rgba(0, 119, 181, 0.4);
    }
    .dev-contact .dev-info {
        display: flex;
        flex-direction: column;
        gap: 1px;
    }
    .dev-contact .dev-name {
        font-size: 0.75rem;
        color: rgba(220, 230, 240, 0.85);
        font-weight: 500;
    }
    .dev-contact .dev-links {
        display: flex;
        align-items: center;
        gap: 4px;
    }
    .dev-contact .dev-email,
    .dev-contact .dev-linkedin {
        font-size: 0.65rem;
        color: rgba(160, 174, 192, 0.5);
        text-decoration: none;
        transition: color 0.2s ease;
    }
    .dev-contact .dev-email:hover,
    .dev-contact .dev-linkedin:hover {
        color: #00d4aa;
    }
    .dev-contact .dev-sep {
        font-size: 0.6rem;
        color: rgba(160, 174, 192, 0.3);
    }

    /* ── Hide Streamlit branding ── */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

# ============================================================
# Constants & API Key
# ============================================================

MODEL = "claude-sonnet-4-5-20250929"
MCP_SERVER_SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "pdb_mcp_server.py")
MCP_PYTHON = sys.executable


def get_api_key():
    """Retrieve API key from Streamlit secrets or environment variable."""
    try:
        return st.secrets["ANTHROPIC_API_KEY"]
    except (KeyError, FileNotFoundError):
        return os.environ.get("ANTHROPIC_API_KEY", "")


# ============================================================
# MCP Client - Connect to the PDB MCP Server
# ============================================================

async def get_mcp_tools():
    """Connect to MCP server and discover available tools."""
    server_params = StdioServerParameters(
        command=MCP_PYTHON,
        args=[MCP_SERVER_SCRIPT],
    )
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools_result = await session.list_tools()
            return tools_result.tools


async def call_mcp_tool(tool_name: str, arguments: dict) -> str:
    """Call a tool on the MCP server and return the result."""
    server_params = StdioServerParameters(
        command=MCP_PYTHON,
        args=[MCP_SERVER_SCRIPT],
    )
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            # For tools that reference a structure by pdb_id, upload cached
            # data first so the server has modified structures available.
            NEEDS_STRUCTURE = {"list_hetatm", "get_structure_info", "get_modified_structure",
                               "calculate_pka", "get_protonation_states"}
            if tool_name in NEEDS_STRUCTURE:
                source_id = arguments.get("pdb_id", arguments.get("structure_id", "")).upper()
                if source_id and source_id in st.session_state.pdb_cache:
                    tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".pdb", delete=False)
                    tmp.write(st.session_state.pdb_cache[source_id])
                    tmp.close()
                    try:
                        await session.call_tool("upload_structure", {
                            "structure_id": source_id,
                            "file_path": tmp.name,
                        })
                    finally:
                        os.unlink(tmp.name)

            result = await session.call_tool(tool_name, arguments)
            texts = []
            for content in result.content:
                if hasattr(content, "text"):
                    texts.append(content.text)
            return "\n".join(texts) if texts else ""


async def call_mcp_tool_and_fetch(tool_name: str, arguments: dict) -> tuple:
    """Call a modification tool AND get_modified_structure in the SAME session.
    Returns (tool_result_text, modified_pdb_text_or_None).
    This is needed because each MCP session is a separate subprocess,
    and modified structures are lost when the subprocess exits.
    Before calling the modification tool, uploads any cached PDB data
    so the server has the previously modified structure available."""
    server_params = StdioServerParameters(
        command=MCP_PYTHON,
        args=[MCP_SERVER_SCRIPT],
    )
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            # Upload the source structure (the pdb_id being modified) so the
            # server has it in memory even though this is a fresh subprocess.
            # Uses a temp file to avoid sending large PDB text through MCP JSON.
            source_id = arguments.get("pdb_id", "").upper()
            tmp_path = None
            if source_id and source_id in st.session_state.pdb_cache:
                tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".pdb", delete=False)
                tmp.write(st.session_state.pdb_cache[source_id])
                tmp.close()
                tmp_path = tmp.name
                await session.call_tool("upload_structure", {
                    "structure_id": source_id,
                    "file_path": tmp_path,
                })

            # Call the modification tool
            result = await session.call_tool(tool_name, arguments)
            texts = []
            for content in result.content:
                if hasattr(content, "text"):
                    texts.append(content.text)
            tool_result = "\n".join(texts) if texts else ""

            # Try to parse and fetch modified structure in same session
            pdb_text = None
            try:
                data = json.loads(tool_result)
                new_id = data.get("new_id")
                if new_id and data.get("status") == "success":
                    fetch_result = await session.call_tool(
                        "get_modified_structure", {"structure_id": new_id}
                    )
                    fetch_texts = []
                    for content in fetch_result.content:
                        if hasattr(content, "text"):
                            fetch_texts.append(content.text)
                    fetched = "\n".join(fetch_texts) if fetch_texts else ""
                    if fetched and not fetched.startswith("{"):
                        pdb_text = fetched
            except (json.JSONDecodeError, TypeError):
                pass
            finally:
                if tmp_path and os.path.exists(tmp_path):
                    os.unlink(tmp_path)

            return tool_result, pdb_text


def run_async(coro):
    """Run an async function from sync context."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


# ============================================================
# Tool Discovery & Conversion
# ============================================================

def discover_tools():
    """Discover MCP tools and convert to Claude API format."""
    if "mcp_tools" in st.session_state and st.session_state.mcp_tools:
        return st.session_state.mcp_tools, st.session_state.claude_tools

    mcp_tools = run_async(get_mcp_tools())
    st.session_state.mcp_tools = mcp_tools

    # Internal tools that Claude should not call directly
    INTERNAL_TOOLS = {"upload_structure"}

    claude_tools = []
    for tool in mcp_tools:
        if tool.name in INTERNAL_TOOLS:
            continue
        claude_tool = {
            "name": tool.name,
            "description": tool.description or "",
            "input_schema": tool.inputSchema if tool.inputSchema else {"type": "object", "properties": {}},
        }
        claude_tools.append(claude_tool)

    # Add local 3D viewer tool (UI-only, not on MCP server)
    claude_tools.append({
        "name": "show_structure_3d",
        "description": "Show interactive 3D visualization of a structure. Call get_modified_structure or download_structure first to get PDB data, then call this with the PDB ID.",
        "input_schema": {
            "type": "object",
            "properties": {
                "structure_id": {"type": "string", "description": "Structure ID to visualize"},
                "style": {"type": "string", "enum": ["cartoon", "stick", "sphere", "line"], "default": "cartoon"},
                "color_scheme": {"type": "string", "enum": ["spectrum", "chain", "ssType"], "default": "spectrum"},
                "highlight_by_name": {"type": "array", "items": {"type": "string"},
                                      "description": "Residue types to highlight as sticks, e.g. ['PRO','HIS']"},
            },
            "required": ["structure_id"],
        },
    })

    st.session_state.claude_tools = claude_tools
    return mcp_tools, claude_tools


# ============================================================
# 3D Viewer
# ============================================================

def generate_viewer_html(structure_id, pdb_data, style="cartoon", color_scheme="spectrum",
                         highlight_by_name=None):
    """Generate py3Dmol HTML string for rendering."""
    viewer = py3Dmol.view(width="100%", height=400)
    viewer.addModel(pdb_data, "pdb")

    style_map = {
        "cartoon": {"cartoon": {"color": color_scheme}},
        "stick": {"stick": {}},
        "sphere": {"sphere": {"radius": 0.4}},
        "line": {"line": {}},
    }
    viewer.setStyle(style_map.get(style, {"cartoon": {"color": color_scheme}}))

    # Metals as red spheres
    for metal in ["ZN", "CO", "FE", "MN", "CU", "NI", "MG"]:
        viewer.addStyle({"elem": metal}, {"sphere": {"radius": 1.2, "color": "#ff6b6b"}})

    # HETATM as sticks
    viewer.addStyle({"hetflag": True}, {"stick": {"radius": 0.12}})

    # Highlight specific residues
    if highlight_by_name:
        for resname in highlight_by_name:
            viewer.addStyle({"resn": resname.upper()},
                            {"stick": {"colorscheme": "greenCarbon", "radius": 0.15}})

    viewer.setBackgroundColor("#0e1117")
    viewer.zoomTo()

    return f'<div class="viewer-container">{viewer._make_html()}</div>'


def show_3d_viewer(structure_id, pdb_data, style="cartoon", color_scheme="spectrum",
                   highlight_by_name=None, label=""):
    """Update session state so the right panel shows this structure."""
    st.session_state.pdb_cache[structure_id] = pdb_data
    st.session_state.current_structure_id = structure_id

    # Add to modification history if not already there
    if not any(m["id"] == structure_id for m in st.session_state.modification_history):
        st.session_state.modification_history.append({
            "id": structure_id,
            "label": label or structure_id,
        })


# ============================================================
# Tool Execution (routes to MCP or local)
# ============================================================

def _build_modification_label(tool_name, tool_input):
    """Build a human-readable label for a modification step."""
    if tool_name == "remove_hetatm":
        removed = tool_input.get("residue_names", [])
        return f"Removed {', '.join(removed)}"
    elif tool_name == "remove_chain":
        chains = tool_input.get("chain_ids", [])
        return f"Removed chain(s) {', '.join(chains)}"
    elif tool_name == "replace_metal":
        return f"{tool_input.get('old_metal', '?')} → {tool_input.get('new_metal', '?')}"
    elif tool_name == "mutate_residue":
        return f"Mutate res {tool_input.get('residue_number', '?')} to {tool_input.get('new_residue', '?')}"
    return "Modified"


def execute_tool(tool_name, tool_input):
    """Execute tool - routes to MCP server or local handler."""

    # Local UI-only tool
    if tool_name == "show_structure_3d":
        sid = tool_input["structure_id"].upper()
        pdb_data = st.session_state.pdb_cache.get(sid)
        if not pdb_data:
            return json.dumps({"error": f"No PDB data cached for {sid}. Download or modify it first."})
        show_3d_viewer(sid, pdb_data,
                       style=tool_input.get("style", "cartoon"),
                       color_scheme=tool_input.get("color_scheme", "spectrum"),
                       highlight_by_name=tool_input.get("highlight_by_name"),
                       label=sid)
        return json.dumps({"status": "success", "message": f"3D viewer updated to show {sid}."})

    # Check if download_structure is requesting an already-cached structure (e.g. uploaded)
    if tool_name == "download_structure":
        pdb_id = tool_input.get("pdb_id", "").upper()
        if pdb_id in st.session_state.pdb_cache:
            data = st.session_state.pdb_cache[pdb_id]
            lines = data.splitlines()
            atoms = sum(1 for l in lines if l.startswith(("ATOM", "HETATM")))
            st.session_state.current_structure_id = pdb_id
            if not any(m["id"] == pdb_id for m in st.session_state.modification_history):
                st.session_state.modification_history.append({
                    "id": pdb_id, "label": f"Original: {pdb_id}",
                })
            return json.dumps({"status": "success", "pdb_id": pdb_id,
                               "lines": len(lines), "atom_records": atoms,
                               "source": "cached"})

    # Modification tools need to fetch PDB text in the same MCP session
    MODIFICATION_TOOLS = {"remove_hetatm", "remove_chain", "replace_metal", "mutate_residue", "add_hydrogens"}

    if tool_name in MODIFICATION_TOOLS:
        result, pdb_text = run_async(call_mcp_tool_and_fetch(tool_name, tool_input))
        if pdb_text:
            try:
                data = json.loads(result)
                new_id = data.get("new_id")
                if new_id:
                    st.session_state.pdb_cache[new_id] = pdb_text
                    st.session_state.current_structure_id = new_id
                    label = _build_modification_label(tool_name, tool_input)
                    if not any(m["id"] == new_id for m in st.session_state.modification_history):
                        st.session_state.modification_history.append({
                            "id": new_id, "label": label,
                        })
            except (json.JSONDecodeError, TypeError):
                pass
    else:
        # Non-modification tools → simple MCP call
        result = run_async(call_mcp_tool(tool_name, tool_input))

    # If it's a download_structure, the result IS the PDB text
    if tool_name == "download_structure" and not result.startswith("{"):
        pdb_id = tool_input.get("pdb_id", "").upper()
        st.session_state.pdb_cache[pdb_id] = result
        st.session_state.current_structure_id = pdb_id
        if not any(m["id"] == pdb_id for m in st.session_state.modification_history):
            st.session_state.modification_history.append({
                "id": pdb_id, "label": f"Original: {pdb_id}",
            })
        lines = result.splitlines()
        atoms = sum(1 for l in lines if l.startswith(("ATOM", "HETATM")))
        return json.dumps({"status": "success", "pdb_id": pdb_id,
                           "lines": len(lines), "atom_records": atoms})

    return result


# ============================================================
# Agent Loop
# ============================================================

SYSTEM_PROMPT = """You are ProteinChat AI, a structural biology assistant powered by MCP (Model Context Protocol).
You connect to a PDB MCP Server that gives you tools for protein structure analysis and modification.

Keep answers SHORT (2-4 sentences). Let the 3D viewer and data speak.

Your MCP tools:
1. search_structures - Search PDB by keyword
2. get_structure_info - Get details for a PDB ID
3. download_structure - Download PDB file (MUST do before 3D view or modification)
4. get_structure_quality - Quality metrics
5. search_by_uniprot - Search by UniProt ID
6. list_hetatm - List ligands/ions/water in a structure
7. remove_hetatm - Remove ligands/ions/water (call list_hetatm first)
8. remove_chain - Remove chains
9. replace_metal - Swap metals (e.g., Co→Zn)
10. mutate_residue - Mutate amino acids
11. get_modified_structure - Get PDB text of a modified structure

Local tool:
- show_structure_3d - Show 3D viewer (call download_structure first)

Rules:
- download_structure BEFORE any visualization or modification
- After modifications, call show_structure_3d to display result
- When removing ligands, call list_hetatm first
- NEVER say user needs external software - YOU can do all edits
"""


def run_agent(user_message, api_key, claude_tools):
    """Run Claude agent loop with MCP tools."""
    client = anthropic.Anthropic(api_key=api_key)

    messages = []
    for msg in st.session_state.chat_history:
        if msg["role"] in ("user", "assistant") and isinstance(msg["content"], str):
            messages.append({"role": msg["role"], "content": msg["content"]})
    messages.append({"role": "user", "content": user_message})

    full_text = ""
    tool_calls_made = []

    for _ in range(15):
        response = client.messages.create(
            model=MODEL, max_tokens=1024, system=SYSTEM_PROMPT,
            tools=claude_tools, messages=messages,
        )

        text_parts = []
        tool_uses = []
        for block in response.content:
            if block.type == "text":
                text_parts.append(block.text)
            elif block.type == "tool_use":
                tool_uses.append(block)

        if text_parts:
            full_text += "\n".join(text_parts)

        if response.stop_reason == "end_of_turn" or not tool_uses:
            break

        messages.append({"role": "assistant", "content": response.content})
        tool_results = []
        for tu in tool_uses:
            result = execute_tool(tu.name, tu.input)
            tool_calls_made.append({"tool": tu.name, "input": tu.input, "result": result})
            tool_results.append({"type": "tool_result", "tool_use_id": tu.id, "content": result})
        messages.append({"role": "user", "content": tool_results})

    return full_text, tool_calls_made


# ============================================================
# Left Panel
# ============================================================

def _get_conversation_title(chat_history):
    """Generate a title from the first user message in a conversation."""
    for msg in chat_history:
        if msg["role"] == "user":
            text = msg["content"]
            return text[:40] + ("..." if len(text) > 40 else "")
    return "New conversation"


def _save_current_conversation():
    """Save current chat to saved_conversations if it has messages.
    Skips saving if the current chat was loaded from history or demo."""
    if not st.session_state.chat_history:
        return
    if st.session_state.get("_loaded_conv_id"):
        # Current chat was loaded from history/demo — don't duplicate it
        st.session_state._loaded_conv_id = None
        return
    title = _get_conversation_title(st.session_state.chat_history)
    conv = {
        "id": str(uuid.uuid4()),
        "title": title,
        "chat_history": list(st.session_state.chat_history),
        "pdb_cache": dict(st.session_state.pdb_cache),
        "modification_history": list(st.session_state.modification_history),
        "current_structure_id": st.session_state.current_structure_id,
    }
    st.session_state.saved_conversations.insert(0, conv)


def _load_conversation(conv):
    """Load a saved conversation into the active session."""
    st.session_state.chat_history = list(conv["chat_history"])
    st.session_state.pdb_cache = dict(conv["pdb_cache"])
    st.session_state.modification_history = list(conv["modification_history"])
    st.session_state.current_structure_id = conv["current_structure_id"]
    st.session_state.pending_viewers = []
    st.session_state._loaded_conv_id = conv["id"]


def _start_new_chat():
    """Save current conversation and start a fresh one."""
    _save_current_conversation()
    st.session_state.chat_history = []
    st.session_state.pdb_cache = {}
    st.session_state.pending_viewers = []
    st.session_state.modification_history = []
    st.session_state.current_structure_id = None
    st.session_state._demo_loaded = False


def render_left_panel():
    """Render left panel: conversation history."""
    # New Chat button at top of left panel
    st.markdown('<div class="new-chat-row">', unsafe_allow_html=True)
    if st.button("+ New Chat", key="new_chat_btn", use_container_width=True):
        _start_new_chat()
        st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

    # Fixed demo example
    st.markdown('<div class="section-header">Demo</div>', unsafe_allow_html=True)
    if st.button("🧬 Visualize 6M8F", key="demo_conv_btn", use_container_width=True):
        _load_demo_conversation()
        st.rerun()

    st.markdown('<div class="gradient-divider"></div>', unsafe_allow_html=True)

    # Saved conversations list
    if st.session_state.saved_conversations:
        st.markdown('<div class="section-header">History</div>', unsafe_allow_html=True)
        for i, conv in enumerate(st.session_state.saved_conversations):
            col_title, col_del = st.columns([5, 1])
            with col_title:
                if st.button(conv["title"], key=f"conv_{conv['id']}", use_container_width=True):
                    _load_conversation(conv)
                    st.rerun()
            with col_del:
                if st.button("🗑", key=f"del_{conv['id']}", use_container_width=True):
                    st.session_state.saved_conversations.pop(i)
                    st.rerun()
    else:
        st.caption("No conversations yet.")



# ============================================================
# Center Panel
# ============================================================

def _on_input_submit():
    """Callback: capture the text_input value into session state and clear the widget."""
    value = st.session_state.get("center_input", "").strip()
    if value:
        st.session_state._submitted_input = value
    # Clear the widget so it doesn't re-trigger on next rerun
    st.session_state.center_input = ""


def render_center_panel():
    """Render center panel: chat conversation. Returns user input text or None."""
    chat_container = st.container(height=550)

    with chat_container:
        if not st.session_state.chat_history:
            # Welcome message
            st.markdown("""
                <div class="welcome-wrapper">
                    <div class="welcome-content">
                        <div class="welcome-icon">🧬</div>
                        <div class="welcome-title">Welcome to ProteinChat AI</div>
                        <div class="welcome-sub">Ask me anything about protein structures</div>
                        <div class="welcome-examples">
                            <div class="welcome-example">Download &amp; visualize a structure</div>
                            <div class="welcome-example">Search proteins by keyword</div>
                            <div class="welcome-example">Modify a PDB file</div>
                            <div class="welcome-example">Calculate pKa values</div>
                            <div class="welcome-example">Add hydrogens to a structure</div>
                            <div class="welcome-example">Analyze residues &amp; chains</div>
                        </div>
                    </div>
                </div>
            """, unsafe_allow_html=True)
        else:
            for msg in st.session_state.chat_history:
                if msg["role"] == "user":
                    with st.chat_message("user"):
                        st.markdown(msg["content"])
                elif msg["role"] == "assistant":
                    with st.chat_message("assistant"):
                        st.markdown(msg["content"])
                        if msg.get("structure_ids"):
                            for sid in msg["structure_ids"]:
                                st.markdown(
                                    f'<div class="structure-notice">Structure <b>{sid}</b> updated — see right panel</div>',
                                    unsafe_allow_html=True,
                                )
            # Show typing indicator while waiting for response
            if st.session_state.get("_waiting_for_response"):
                with st.chat_message("assistant"):
                    st.markdown(
                        '<div class="typing-indicator"><span></span><span></span><span></span></div>',
                        unsafe_allow_html=True,
                    )

    # Input always below the container, inside the center column
    st.text_input(
        "Ask about proteins...",
        placeholder="Ask about protein structures...",
        key="center_input",
        label_visibility="collapsed",
        on_change=_on_input_submit,
    )

    # Developer contact below chat input
    # Load avatar image as base64 if available
    avatar_html = ""
    app_dir = os.path.dirname(os.path.abspath(__file__))
    avatar_path = None
    for name in ("avatar", "Avatar"):
        for ext in ("jpg", "jpeg", "png", "webp", "JPG", "PNG"):
            candidate = os.path.join(app_dir, f"{name}.{ext}")
            if os.path.exists(candidate):
                avatar_path = candidate
                break
        if avatar_path:
            break
    if avatar_path:
        import base64
        with open(avatar_path, "rb") as img_f:
            b64 = base64.b64encode(img_f.read()).decode()
        mime = "image/png" if avatar_path.endswith(".png") else "image/jpeg"
        avatar_html = f'<div class="dev-avatar"><img src="data:{mime};base64,{b64}" alt="ST" /></div>'
    else:
        avatar_html = '<div class="dev-avatar"><span>ST</span></div>'

    st.markdown(f"""
        <div class="dev-contact">
            <div class="dev-row">
                {avatar_html}
                <div class="dev-info">
                    <span class="dev-name">Developed by Sana Tavasoli</span>
                    <span class="dev-links">
                        <a href="mailto:stavasol96@gmail.com" class="dev-email">stavasol96@gmail.com</a>
                        <span class="dev-sep">·</span>
                        <a href="https://www.linkedin.com/in/sana-tavasoli-4a17b0373/" target="_blank" class="dev-linkedin">LinkedIn</a>
                    </span>
                </div>
            </div>
        </div>
    """, unsafe_allow_html=True)



# ============================================================
# Right Panel
# ============================================================

def render_right_panel():
    """Render right panel: 3D viewer, downloads, modification steps."""
    st.markdown('<div class="section-header">3D Structure Viewer</div>', unsafe_allow_html=True)

    current_id = st.session_state.current_structure_id
    if current_id and current_id in st.session_state.pdb_cache:
        pdb_data = st.session_state.pdb_cache[current_id]

        # Style selectors
        col_style, col_color = st.columns(2)
        with col_style:
            style = st.selectbox("Style", ["cartoon", "stick", "sphere", "line"],
                                 key="viewer_style", label_visibility="collapsed")
        with col_color:
            color = st.selectbox("Color", ["spectrum", "chain", "ssType"],
                                 key="viewer_color", label_visibility="collapsed")

        # 3D Viewer
        viewer_html = generate_viewer_html(current_id, pdb_data, style, color)
        components.html(viewer_html, height=420, scrolling=False)

        st.caption(f"Showing: **{current_id}**")

        # Download current structure
        st.download_button(
            f"Download {current_id}.pdb",
            data=pdb_data,
            file_name=f"{current_id}.pdb",
            mime="chemical/x-pdb",
            key=f"dl_current_{current_id}",
            use_container_width=True,
            type="primary",
        )

        # Modification history dropdown (exclude demo entries)
        real_steps = [
            s for s in st.session_state.modification_history
            if not s["label"].startswith("Demo:")
        ]
        if len(real_steps) > 1:
            st.markdown('<div class="gradient-divider"></div>', unsafe_allow_html=True)
            st.markdown('<div class="section-header">Versions</div>', unsafe_allow_html=True)

            options = [
                f"Step {i+1}: {step['label']}"
                for i, step in enumerate(real_steps)
            ]
            current_idx = 0
            for i, step in enumerate(real_steps):
                if step["id"] == current_id:
                    current_idx = i
                    break

            selected = st.selectbox(
                "Version",
                options,
                index=current_idx,
                key="version_select",
                label_visibility="collapsed",
            )

            sel_idx = options.index(selected)
            sel_id = real_steps[sel_idx]["id"]
            if sel_id != current_id and sel_id in st.session_state.pdb_cache:
                st.session_state.current_structure_id = sel_id
                st.rerun()
    else:
        st.markdown(
            '<div class="viewer-empty">'
            '<div><div class="icon">🧬</div>'
            'Ask to download a structure<br>or upload a PDB file to visualize</div></div>',
            unsafe_allow_html=True,
        )


# ============================================================
# Input Handling
# ============================================================

def _process_response(user_input, api_key, claude_tools):
    """Call the AI agent and append the assistant response to chat history.
    The user message should already be in chat_history before calling this."""
    try:
        response_text, tool_calls = run_agent(user_input, api_key, claude_tools)

        # Collect structure IDs that were modified/downloaded
        structure_ids = []
        for tc in tool_calls:
            try:
                r = json.loads(tc["result"])
                sid = r.get("new_id") or r.get("pdb_id")
                if sid:
                    structure_ids.append(sid)
            except (json.JSONDecodeError, TypeError):
                pass

        st.session_state.chat_history.append({
            "role": "assistant",
            "content": response_text or "(completed)",
            "structure_ids": structure_ids,
        })

    except anthropic.AuthenticationError:
        st.session_state.chat_history.append({
            "role": "assistant", "content": "Error: Invalid API key. Please check your configuration.",
        })
    except anthropic.RateLimitError:
        st.session_state.chat_history.append({
            "role": "assistant", "content": "Error: Rate limit reached. Please wait and try again.",
        })
    except Exception as e:
        st.session_state.chat_history.append({
            "role": "assistant", "content": f"Error: {e}",
        })


# ============================================================
# Demo Conversation Loader
# ============================================================

DEMO_JSON = os.path.join(os.path.dirname(os.path.abspath(__file__)), "demo_conversation.json")


@st.cache_data(show_spinner=False)
def _load_demo_json():
    """Load the pre-generated demo conversation JSON (cached)."""
    if os.path.exists(DEMO_JSON):
        with open(DEMO_JSON, "r") as f:
            return json.load(f)
    return None


def _load_demo_conversation():
    """Load the demo conversation into the active session."""
    demo = _load_demo_json()
    if not demo:
        return
    st.session_state.chat_history = list(demo["chat_history"])
    st.session_state.pdb_cache = dict(demo["pdb_cache"])
    st.session_state.modification_history = list(demo["modification_history"])
    st.session_state.current_structure_id = demo["current_structure_id"]
    st.session_state.pending_viewers = []
    st.session_state._loaded_conv_id = "demo"


def _load_demo_structure_on_start():
    """On first visit (no chat yet), show demo structure in viewer."""
    if st.session_state.current_structure_id is not None:
        return
    if st.session_state.get("_demo_loaded"):
        return
    demo = _load_demo_json()
    if demo:
        # Just load the original 6M8F for the viewer, not the full conversation
        first_id = demo["modification_history"][0]["id"]
        if first_id in demo["pdb_cache"]:
            st.session_state.pdb_cache[first_id] = demo["pdb_cache"][first_id]
            st.session_state.current_structure_id = first_id
            st.session_state.modification_history = [
                {"id": first_id, "label": f"Demo: {first_id}"}
            ]
    st.session_state._demo_loaded = True


# ============================================================
# Main
# ============================================================

def main():
    # Initialize session state
    defaults = {
        "chat_history": [],
        "pdb_cache": {},
        "pending_viewers": [],
        "pending_example": None,
        "mcp_tools": None,
        "claude_tools": None,
        "modification_history": [],
        "current_structure_id": None,
        "saved_conversations": [],
        "_submitted_input": None,
        "_waiting_for_response": None,
    }
    for key, default in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = default

    # Load demo structure on first visit
    _load_demo_structure_on_start()

    # Get API key (hidden from user)
    api_key = get_api_key()
    if not api_key:
        st.error("No API key configured. Set ANTHROPIC_API_KEY in .streamlit/secrets.toml or as an environment variable.")
        st.stop()

    # Discover MCP tools
    try:
        mcp_tools, claude_tools = discover_tools()
    except Exception as e:
        st.error(f"Failed to connect to MCP server: {e}")
        st.info("Make sure pdb_mcp_server.py is at: " + MCP_SERVER_SCRIPT)
        st.stop()

    # App header
    st.markdown("""
        <div class="app-header">
            <h1>ProteinChat AI</h1>
            <p>MCP Protocol &bull; PDB Search &bull; 3D Viewer &bull; Structure Editing &bull; PROPKA</p>
        </div>
    """, unsafe_allow_html=True)

    # --- Three-panel layout ---
    left_col, center_col, right_col = st.columns([1.2, 2.5, 2.0], gap="medium")

    with left_col:
        render_left_panel()

    with center_col:
        render_center_panel()

    with right_col:
        render_right_panel()

    # Phase 1: New input received → add user message, show it, then trigger Phase 2
    new_input = None
    if st.session_state.pending_example:
        new_input = st.session_state.pending_example
        st.session_state.pending_example = None
    elif st.session_state.get("_submitted_input"):
        new_input = st.session_state._submitted_input
        st.session_state._submitted_input = None

    if new_input:
        # Add user message immediately so it shows on next rerun
        st.session_state.chat_history.append({"role": "user", "content": new_input})
        st.session_state._waiting_for_response = new_input
        st.rerun()

    # Phase 2: User message is visible, now fetch the AI response
    if st.session_state.get("_waiting_for_response"):
        pending_msg = st.session_state._waiting_for_response
        st.session_state._waiting_for_response = None
        _process_response(pending_msg, api_key, claude_tools)
        st.rerun()


if __name__ == "__main__":
    main()
