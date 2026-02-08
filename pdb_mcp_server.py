#!/usr/bin/env python3
"""
PDB MCP Server - Structural Biology Agent Tools

A Model Context Protocol server for protein structure search,
retrieval, analysis, and modification via the RCSB PDB.

Tools provided:
  1. search_structures     - Search PDB by keyword
  2. get_structure_info    - Get details for a PDB ID
  3. download_structure    - Download coordinate files
  4. search_by_uniprot     - Find structures by UniProt ID
  5. get_structure_quality  - Get validation metrics
  6. upload_structure      - Upload PDB data for chaining modifications
  7. list_hetatm           - List ligands/ions/water in a structure
  8. remove_hetatm         - Remove ligands/ions/water from a structure
  9. remove_chain          - Remove chains from a structure
  10. replace_metal         - Swap metal ions in a structure
  11. mutate_residue       - Mutate amino acid residues
  12. get_modified_structure - Get PDB text of modified structure
  13. calculate_pka        - Predict pKa values using PROPKA
  14. get_protonation_states - Get protonation states at a given pH
  15. add_hydrogens         - Add hydrogens at correct protonation states (PDB2PQR)
"""

import json
import re
import os
import tempfile
from typing import Optional, List

import requests
from mcp.server.fastmcp import FastMCP

# ============================================================
# Server Setup
# ============================================================

mcp = FastMCP(
    "PDB Server",
    instructions="Access the Protein Data Bank (PDB) for protein structure search, retrieval, and validation."
)

# API Configuration
PDB_DATA_API = "https://data.rcsb.org/rest/v1"
PDB_SEARCH_API = "https://search.rcsb.org/rcsbsearch/v2"
PDB_FILES_URL = "https://files.rcsb.org/download"
HEADERS = {
    "User-Agent": "PDB-MCP-Server-Python/1.0.0",
    "Accept": "application/json",
}


# ============================================================
# Validation
# ============================================================

def is_valid_pdb_id(pdb_id: str) -> bool:
    """Validate a PDB ID (4-char code starting with a digit)."""
    return isinstance(pdb_id, str) and bool(re.match(r"^[0-9][a-zA-Z0-9]{3}$", pdb_id))


# ============================================================
# Tool 1: Search Structures
# ============================================================

@mcp.tool()
def search_structures(
    query: str,
    limit: int = 25,
    sort_by: str = "score",
    experimental_method: Optional[str] = None,
    resolution_range: Optional[str] = None,
) -> str:
    """
    Search PDB database for protein structures by keyword, protein name, or PDB ID.

    Args:
        query: Search query (protein name, keyword, PDB ID, etc.)
        limit: Number of results to return (1-1000, default: 25)
        sort_by: Sort results by (release_date, resolution, score)
        experimental_method: Filter by method (X-RAY DIFFRACTION, ELECTRON MICROSCOPY, NMR)
        resolution_range: Resolution range filter (e.g., "1.0-2.0")
    """
    search_body = {
        "query": {
            "type": "terminal",
            "service": "full_text",
            "parameters": {"value": query},
        },
        "return_type": "entry",
        "request_options": {
            "paginate": {"start": 0, "rows": min(limit, 1000)},
            "results_content_type": ["experimental"],
            "sort": [{"sort_by": sort_by, "direction": "desc"}],
        },
    }

    filters = []
    if experimental_method:
        filters.append({
            "type": "terminal",
            "service": "text",
            "parameters": {
                "attribute": "exptl.method",
                "operator": "exact_match",
                "value": experimental_method,
            },
        })

    if resolution_range:
        parts = resolution_range.split("-")
        if len(parts) == 2:
            try:
                min_res, max_res = float(parts[0]), float(parts[1])
                filters.append({
                    "type": "terminal",
                    "service": "text",
                    "parameters": {
                        "attribute": "rcsb_entry_info.resolution_combined",
                        "operator": "range",
                        "value": {
                            "from": min_res,
                            "to": max_res,
                            "include_lower": True,
                            "include_upper": True,
                        },
                    },
                })
            except ValueError:
                pass

    if filters:
        search_body["query"] = {
            "type": "group",
            "logical_operator": "and",
            "nodes": [search_body["query"]] + filters,
        }

    try:
        response = requests.post(
            f"{PDB_SEARCH_API}/query",
            json=search_body,
            headers=HEADERS,
            timeout=30,
        )
        response.raise_for_status()
        return json.dumps(response.json(), indent=2)
    except requests.RequestException as e:
        return json.dumps({"error": f"Search failed: {str(e)}"})


# ============================================================
# Tool 2: Get Structure Info
# ============================================================

@mcp.tool()
def get_structure_info(pdb_id: str, format: str = "json") -> str:
    """
    Get detailed information for a specific PDB structure.

    Args:
        pdb_id: PDB ID (4-character code, e.g., "1ABC")
        format: Output format - "json", "pdb", "mmcif", or "xml"
    """
    if not is_valid_pdb_id(pdb_id):
        return json.dumps({"error": f"Invalid PDB ID: {pdb_id}"})

    pdb_id_lower = pdb_id.lower()

    try:
        if format == "json":
            response = requests.get(
                f"{PDB_DATA_API}/core/entry/{pdb_id_lower}",
                headers=HEADERS,
                timeout=30,
            )
            response.raise_for_status()
            return json.dumps(response.json(), indent=2)
        else:
            extension = "cif" if format == "mmcif" else format
            url = f"{PDB_FILES_URL}/{pdb_id_lower}.{extension}"
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            return response.text
    except requests.RequestException as e:
        return json.dumps({"error": f"Failed to fetch structure {pdb_id}: {str(e)}"})


# ============================================================
# Tool 3: Download Structure
# ============================================================

@mcp.tool()
def download_structure(
    pdb_id: str,
    format: str = "pdb",
    assembly_id: Optional[str] = None,
) -> str:
    """
    Download structure coordinates in various formats.

    Args:
        pdb_id: PDB ID (4-character code)
        format: File format - "pdb", "mmcif", "mmtf", or "xml"
        assembly_id: Biological assembly ID (optional)
    """
    if not is_valid_pdb_id(pdb_id):
        return json.dumps({"error": f"Invalid PDB ID: {pdb_id}"})

    pdb_id_lower = pdb_id.lower()
    extension = "cif" if format == "mmcif" else format

    if assembly_id:
        url = f"{PDB_FILES_URL}/{pdb_id_lower}-assembly{assembly_id}.{extension}"
    else:
        url = f"{PDB_FILES_URL}/{pdb_id_lower}.{extension}"

    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        header = f"Structure file for {pdb_id} ({format.upper()} format)"
        if assembly_id:
            header += f" - Assembly {assembly_id}"
        return f"{header}:\n\n{response.text}"
    except requests.RequestException as e:
        return json.dumps({"error": f"Download failed: {str(e)}"})


# ============================================================
# Tool 4: Search by UniProt
# ============================================================

@mcp.tool()
def search_by_uniprot(uniprot_id: str, limit: int = 25) -> str:
    """
    Find PDB structures associated with a UniProt accession.

    Args:
        uniprot_id: UniProt accession number (e.g., "P00533" for EGFR)
        limit: Number of results to return (1-1000, default: 25)
    """
    search_body = {
        "query": {
            "type": "terminal",
            "service": "text",
            "parameters": {
                "attribute": "rcsb_polymer_entity_container_identifiers.reference_sequence_identifiers.database_accession",
                "operator": "exact_match",
                "value": uniprot_id,
            },
        },
        "return_type": "entry",
        "request_options": {
            "paginate": {"start": 0, "rows": min(limit, 1000)},
            "results_content_type": ["experimental"],
        },
    }

    try:
        response = requests.post(
            f"{PDB_SEARCH_API}/query",
            json=search_body,
            headers=HEADERS,
            timeout=30,
        )
        response.raise_for_status()
        return json.dumps(response.json(), indent=2)
    except requests.RequestException as e:
        return json.dumps({"error": f"UniProt search failed: {str(e)}"})


# ============================================================
# Tool 5: Get Structure Quality
# ============================================================

@mcp.tool()
def get_structure_quality(pdb_id: str) -> str:
    """
    Get structure quality metrics and validation data for a PDB structure.

    Args:
        pdb_id: PDB ID (4-character code)
    """
    if not is_valid_pdb_id(pdb_id):
        return json.dumps({"error": f"Invalid PDB ID: {pdb_id}"})

    pdb_id_lower = pdb_id.lower()

    try:
        response = requests.get(
            f"{PDB_DATA_API}/core/entry/{pdb_id_lower}",
            headers=HEADERS,
            timeout=30,
        )
        response.raise_for_status()
        entry_data = response.json()

        quality_data = {
            "pdb_id": pdb_id_lower,
            "method": entry_data.get("exptl", [{}])[0].get("method", "Unknown"),
            "resolution": entry_data.get("rcsb_entry_info", {}).get(
                "resolution_combined", None
            ),
        }

        refine = entry_data.get("refine", [{}])
        if refine:
            quality_data["r_work"] = refine[0].get("ls_R_factor_R_work", None)
            quality_data["r_free"] = refine[0].get("ls_R_factor_R_free", None)

        pdbx_vrpt = entry_data.get("pdbx_vrpt_summary", {})
        if pdbx_vrpt:
            quality_data["validation"] = {
                "clashscore": pdbx_vrpt.get("clashscore"),
                "ramachandran_outlier_percent": pdbx_vrpt.get(
                    "percent_ramachandran_outliers_full_length"
                ),
                "rotamer_outlier_percent": pdbx_vrpt.get(
                    "percent_rotamer_outliers_full_length"
                ),
            }

        return json.dumps(quality_data, indent=2)
    except requests.RequestException as e:
        return json.dumps({"error": f"Failed to fetch quality data: {str(e)}"})


# ============================================================
# In-memory structure store (for modifications)
# ============================================================

_structures: dict[str, str] = {}


def _ensure_downloaded(pdb_id: str) -> str:
    """Make sure a structure is in memory. Returns the key."""
    key = pdb_id.upper()
    if key not in _structures:
        if not is_valid_pdb_id(key):
            return ""
        url = f"{PDB_FILES_URL}/{key.lower()}.pdb"
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        _structures[key] = resp.text
    return key


# ============================================================
# Tool: Upload Structure (for chaining modifications)
# ============================================================

@mcp.tool()
def upload_structure(structure_id: str, file_path: str) -> str:
    """
    Load a PDB structure from a temp file into memory for modification tools.

    The client writes PDB data to a temp file and passes the path here.
    This avoids sending large PDB text through the MCP JSON pipe.

    Args:
        structure_id: Structure ID (e.g., "1HPX_NOSO4")
        file_path: Path to the temp file containing PDB data
    """
    key = structure_id.upper()
    try:
        with open(file_path, "r") as f:
            pdb_data = f.read()
    except FileNotFoundError:
        return json.dumps({"error": f"File not found: {file_path}"})
    _structures[key] = pdb_data
    lines = pdb_data.splitlines()
    atoms = sum(1 for l in lines if l.startswith(("ATOM", "HETATM")))
    return json.dumps({
        "status": "success",
        "structure_id": key,
        "lines": len(lines),
        "atom_records": atoms,
    })


# ============================================================
# Tool 6: List HETATM
# ============================================================

@mcp.tool()
def list_hetatm(pdb_id: str) -> str:
    """
    List all HETATM residues (ligands, ions, water) and chains in a PDB structure.

    Args:
        pdb_id: PDB ID or modified structure ID (e.g., "1YOG" or "1YOG_noSO4")
    """
    key = pdb_id.upper()
    if key not in _structures:
        try:
            key = _ensure_downloaded(pdb_id)
        except Exception:
            return json.dumps({"error": f"Could not load {pdb_id}"})

    pdb_data = _structures[key]
    het_residues = {}
    chains = set()

    for line in pdb_data.splitlines():
        if line.startswith("HETATM"):
            resname = line[17:20].strip()
            chain = line[21].strip()
            resnum = line[22:26].strip()
            chains.add(chain)
            rk = f"{resname}_{chain}_{resnum}"
            if rk not in het_residues:
                het_residues[rk] = {"name": resname, "chain": chain, "number": resnum, "atoms": 0}
            het_residues[rk]["atoms"] += 1
        elif line.startswith("ATOM"):
            chains.add(line[21].strip())

    by_type = {}
    for r in het_residues.values():
        n = r["name"]
        if n not in by_type:
            by_type[n] = {"count": 0, "total_atoms": 0, "chains": set()}
        by_type[n]["count"] += 1
        by_type[n]["total_atoms"] += r["atoms"]
        by_type[n]["chains"].add(r["chain"])

    summary = [{"residue": n, "instances": i["count"], "total_atoms": i["total_atoms"],
                "chains": sorted(i["chains"])} for n, i in sorted(by_type.items())]

    return json.dumps({"pdb_id": key, "chains": sorted(chains),
                        "hetatm_types": summary}, indent=2)


# ============================================================
# Tool 7: Remove HETATM
# ============================================================

@mcp.tool()
def remove_hetatm(
    pdb_id: str,
    residue_names: Optional[List[str]] = None,
    remove_water: bool = False,
) -> str:
    """
    Remove HETATM residues (ligands, ions, water) from a structure.

    Args:
        pdb_id: PDB ID or modified structure ID
        residue_names: 3-letter codes to remove, e.g. ["SO4", "GOL"]
        remove_water: Also remove water (HOH/WAT)
    """
    key = pdb_id.upper()
    if key not in _structures:
        try:
            key = _ensure_downloaded(pdb_id)
        except Exception:
            return json.dumps({"error": f"Could not load {pdb_id}"})

    to_remove = set()
    if residue_names:
        to_remove = {n.upper().strip() for n in residue_names}
    if remove_water:
        to_remove |= {"HOH", "WAT", "DOD"}
    if not to_remove:
        return json.dumps({"error": "Specify residue_names or set remove_water=true"})

    pdb_data = _structures[key]
    new_lines = []
    removed = {}
    for line in pdb_data.splitlines():
        skip = False
        if line.startswith("HETATM"):
            rn = line[17:20].strip()
            if rn in to_remove:
                removed[rn] = removed.get(rn, 0) + 1
                skip = True
        elif line.startswith(("HET ", "HETNAM", "FORMUL", "CONECT")):
            for rn in to_remove:
                if rn in line:
                    skip = True
                    break
        if not skip:
            new_lines.append(line)

    new_key = f"{key}_NO{'_'.join(sorted(to_remove))}"
    _structures[new_key] = "\n".join(new_lines) + "\n"

    return json.dumps({"status": "success", "new_id": new_key,
                        "removed": removed, "total_atoms_removed": sum(removed.values())})


# ============================================================
# Tool 8: Remove Chain
# ============================================================

@mcp.tool()
def remove_chain(pdb_id: str, chain_ids: List[str]) -> str:
    """
    Remove one or more chains from a structure.

    Args:
        pdb_id: PDB ID or modified structure ID
        chain_ids: Chain letters to remove, e.g. ["B", "C"]
    """
    key = pdb_id.upper()
    if key not in _structures:
        try:
            key = _ensure_downloaded(pdb_id)
        except Exception:
            return json.dumps({"error": f"Could not load {pdb_id}"})

    chains = {c.upper() for c in chain_ids}
    pdb_data = _structures[key]
    new_lines = []
    count = 0
    for line in pdb_data.splitlines():
        if line.startswith(("ATOM", "HETATM", "TER", "ANISOU")):
            if len(line) > 21 and line[21] in chains:
                count += 1
                continue
        new_lines.append(line)

    new_key = f"{key}_NO{''.join(sorted(chains))}"
    _structures[new_key] = "\n".join(new_lines) + "\n"
    return json.dumps({"status": "success", "new_id": new_key,
                        "chains_removed": list(chains), "atoms_removed": count})


# ============================================================
# Tool 9: Replace Metal
# ============================================================

ELEMENT_NAMES = {
    "ZN": "ZINC", "CO": "COBALT", "FE": "IRON", "MN": "MANGANESE",
    "CU": "COPPER", "NI": "NICKEL", "MG": "MAGNESIUM", "CA": "CALCIUM",
    "NA": "SODIUM", "K": "POTASSIUM", "CD": "CADMIUM", "HG": "MERCURY",
}

@mcp.tool()
def replace_metal(pdb_id: str, old_metal: str, new_metal: str) -> str:
    """
    Replace a metal ion in a structure (e.g., Co→Zn, Fe→Mn).

    Args:
        pdb_id: PDB ID or modified structure ID
        old_metal: Element symbol to replace (e.g., "CO")
        new_metal: New element symbol (e.g., "ZN")
    """
    key = pdb_id.upper()
    if key not in _structures:
        try:
            key = _ensure_downloaded(pdb_id)
        except Exception:
            return json.dumps({"error": f"Could not load {pdb_id}"})

    old_sym = old_metal.upper().strip()
    new_sym = new_metal.upper().strip()
    pdb_data = _structures[key]
    new_lines = []
    count = 0

    for line in pdb_data.splitlines():
        if line.startswith("HETATM"):
            atom_name = line[12:16].strip()
            element = line[76:78].strip() if len(line) >= 78 else ""
            if atom_name == old_sym or element == old_sym:
                na = f"{new_sym:>2}" if len(new_sym) <= 2 else new_sym[:2]
                line = (line[:12] + f"{na:>4}" + line[16:17] + f"{new_sym:>3}" +
                        line[20:76] + f"{new_sym:>2}" + (line[78:] if len(line) > 78 else ""))
                count += 1
        elif line.startswith("HET ") and f" {old_sym} " in line:
            line = line.replace(f" {old_sym} ", f" {new_sym} ")
        elif line.startswith("HETNAM") and old_sym in line:
            line = line.replace(ELEMENT_NAMES.get(old_sym, old_sym),
                                ELEMENT_NAMES.get(new_sym, new_sym)).replace(old_sym, new_sym)
        elif line.startswith("FORMUL") and old_sym in line:
            line = line.replace(old_sym, new_sym)
        new_lines.append(line)

    new_key = f"{key}_{new_sym}"
    _structures[new_key] = "\n".join(new_lines) + "\n"
    return json.dumps({"status": "success", "new_id": new_key,
                        "old_metal": old_sym, "new_metal": new_sym, "atoms_replaced": count})


# ============================================================
# Tool 10: Mutate Residue
# ============================================================

BACKBONE = {"N", "CA", "C", "O", "CB", "OXT", "H", "HA"}
SIDECHAIN_MAP = {
    "ALA": {"CB"}, "GLY": set(), "SER": {"CB", "OG"}, "CYS": {"CB", "SG"},
    "VAL": {"CB", "CG1", "CG2"}, "THR": {"CB", "OG1", "CG2"},
    "LEU": {"CB", "CG", "CD1", "CD2"}, "ILE": {"CB", "CG1", "CG2", "CD1"},
    "PRO": {"CB", "CG", "CD"},
    "PHE": {"CB", "CG", "CD1", "CD2", "CE1", "CE2", "CZ"},
    "TYR": {"CB", "CG", "CD1", "CD2", "CE1", "CE2", "CZ", "OH"},
    "TRP": {"CB", "CG", "CD1", "CD2", "NE1", "CE2", "CE3", "CZ2", "CZ3", "CH2"},
    "ASP": {"CB", "CG", "OD1", "OD2"}, "GLU": {"CB", "CG", "CD", "OE1", "OE2"},
    "ASN": {"CB", "CG", "OD1", "ND2"}, "GLN": {"CB", "CG", "CD", "OE1", "NE2"},
    "HIS": {"CB", "CG", "ND1", "CD2", "CE1", "NE2"},
    "LYS": {"CB", "CG", "CD", "CE", "NZ"},
    "ARG": {"CB", "CG", "CD", "NE", "CZ", "NH1", "NH2"},
    "MET": {"CB", "CG", "SD", "CE"},
}
ATOM_CONVERT = {
    ("HIS", "SER"): {"CG": "OG"}, ("CYS", "SER"): {"SG": "OG"},
    ("SER", "CYS"): {"OG": "SG"}, ("ASP", "ASN"): {"OD2": "ND2"},
    ("GLU", "GLN"): {"OE2": "NE2"},
}

@mcp.tool()
def mutate_residue(
    pdb_id: str,
    residue_number: int,
    new_residue: str,
    chain_id: str = "",
) -> str:
    """
    Mutate an amino acid residue in a structure.

    Args:
        pdb_id: PDB ID or modified structure ID
        residue_number: Residue number to mutate
        new_residue: New amino acid (3-letter code, e.g., "SER")
        chain_id: Chain ID (leave empty for auto-detect)
    """
    key = pdb_id.upper()
    if key not in _structures:
        try:
            key = _ensure_downloaded(pdb_id)
        except Exception:
            return json.dumps({"error": f"Could not load {pdb_id}"})

    pdb_data = _structures[key]
    res_num = str(residue_number).strip()
    new_res = new_residue.upper().strip()
    allowed = BACKBONE | SIDECHAIN_MAP.get(new_res, set())
    old_res_name = None
    new_lines = []
    mutated = 0

    for line in pdb_data.splitlines():
        if line.startswith(("ATOM", "HETATM")):
            lc = line[21].strip()
            lr = line[22:26].strip()
            an = line[12:16].strip()
            if lr == res_num and (not chain_id or lc == chain_id.upper()):
                if old_res_name is None:
                    old_res_name = line[17:20].strip()
                convert = ATOM_CONVERT.get((old_res_name, new_res), {})
                if an in convert:
                    na = convert[an]
                    line = line[:12] + f" {na:<3}" + line[16:17] + f"{new_res:>3}" + line[20:]
                    new_lines.append(line)
                    mutated += 1
                elif an in allowed:
                    line = line[:17] + f"{new_res:>3}" + line[20:]
                    new_lines.append(line)
                    mutated += 1
                continue
        new_lines.append(line)

    if old_res_name is None:
        return json.dumps({"error": f"Residue {res_num} not found"})

    label = f"{old_res_name[0]}{res_num}{new_res[0]}"
    new_key = f"{key}_{label}"
    _structures[new_key] = "\n".join(new_lines) + "\n"
    return json.dumps({"status": "success", "new_id": new_key,
                        "old_residue": old_res_name, "new_residue": new_res,
                        "atoms_modified": mutated})


# ============================================================
# Tool 11: Get Modified Structure (returns PDB text)
# ============================================================

@mcp.tool()
def get_modified_structure(structure_id: str) -> str:
    """
    Get the PDB file content of a modified structure.

    Args:
        structure_id: Structure ID (e.g., "1YOG_ZN", "1YOG_H93S_noSO4")
    """
    # Try exact key first, then uppercase (base PDB IDs are uppercase,
    # but modified keys contain lowercase parts like "_no", "_H93S")
    key = structure_id
    if key not in _structures:
        key = structure_id.upper()
    if key not in _structures:
        return json.dumps({"error": f"Structure {structure_id} not found in memory"})
    return _structures[key]


# ============================================================
# Tool 12: Calculate pKa (PROPKA)
# ============================================================

# Ionizable residue types we care about
_IONIZABLE = {"ASP", "GLU", "HIS", "CYS", "TYR", "LYS", "ARG", "N+", "C-"}

# Model (reference) pKa values for ionizable residues
_MODEL_PKA = {
    "ASP": 3.80, "GLU": 4.50, "HIS": 6.50, "CYS": 9.00,
    "TYR": 10.00, "LYS": 10.50, "ARG": 12.50, "N+": 8.00, "C-": 3.20,
}


def _run_propka(pdb_text: str) -> list:
    """Run PROPKA on PDB text and return list of pKa results."""
    try:
        import propka.run as pk
    except ImportError:
        raise RuntimeError("PROPKA is not installed. Install with: pip install propka")

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".pdb", delete=False
    ) as f:
        f.write(pdb_text)
        tmpfile = f.name

    try:
        mol = pk.single(tmpfile, write_pka=False)
    finally:
        os.unlink(tmpfile)

    results = []
    # Use the AVR (average) conformation if available, else first
    conf_key = "AVR" if "AVR" in mol.conformations else list(mol.conformations.keys())[0]
    conf = mol.conformations[conf_key]

    for g in conf.groups:
        res_type = g.residue_type.strip()
        if res_type not in _IONIZABLE:
            continue
        pka_val = getattr(g, "pka_value", None)
        if pka_val is None or pka_val == 0.0:
            continue
        model_pka = _MODEL_PKA.get(res_type, 0.0)
        results.append({
            "residue": res_type,
            "chain": g.atom.chain_id,
            "number": g.atom.res_num,
            "pka": round(pka_val, 2),
            "model_pka": model_pka,
            "shift": round(pka_val - model_pka, 2),
        })

    return results


@mcp.tool()
def calculate_pka(pdb_id: str) -> str:
    """
    Calculate pKa values for all ionizable residues using PROPKA.

    Predicts how the protein environment shifts pKa values from their
    model (reference) values. Large shifts indicate residues strongly
    influenced by their surroundings (buried, near charges, H-bonds).

    Args:
        pdb_id: PDB ID or modified structure ID (e.g., "1HPX", "1YOG_ZN")
    """
    key = pdb_id
    if key not in _structures:
        key = pdb_id.upper()
    if key not in _structures:
        try:
            key = _ensure_downloaded(pdb_id)
        except Exception:
            return json.dumps({"error": f"Could not load {pdb_id}"})

    pdb_text = _structures[key]

    try:
        results = _run_propka(pdb_text)
    except RuntimeError as e:
        return json.dumps({"error": str(e)})
    except Exception as e:
        return json.dumps({"error": f"PROPKA calculation failed: {e}"})

    # Sort by absolute shift to highlight most interesting residues
    results.sort(key=lambda r: abs(r["shift"]), reverse=True)

    return json.dumps({
        "status": "success",
        "pdb_id": pdb_id,
        "total_ionizable_residues": len(results),
        "residues": results,
        "note": "pKa values predicted by PROPKA 3. 'shift' = predicted pKa - model pKa. "
                "Large positive shifts mean the protonated form is stabilized; "
                "large negative shifts mean the deprotonated form is stabilized.",
    }, indent=2)


# ============================================================
# Tool 13: Get Protonation States at a Given pH
# ============================================================

@mcp.tool()
def get_protonation_states(pdb_id: str, ph: float = 7.0) -> str:
    """
    Predict protonation states of ionizable residues at a given pH.

    Uses PROPKA pKa values to determine which residues are protonated
    or deprotonated at the specified pH. Useful for understanding
    charge states relevant to enzyme mechanisms and binding.

    Args:
        pdb_id: PDB ID or modified structure ID
        ph: pH value (default 7.0)
    """
    key = pdb_id
    if key not in _structures:
        key = pdb_id.upper()
    if key not in _structures:
        try:
            key = _ensure_downloaded(pdb_id)
        except Exception:
            return json.dumps({"error": f"Could not load {pdb_id}"})

    pdb_text = _structures[key]

    try:
        results = _run_propka(pdb_text)
    except RuntimeError as e:
        return json.dumps({"error": str(e)})
    except Exception as e:
        return json.dumps({"error": f"PROPKA calculation failed: {e}"})

    # Determine protonation: acidic residues (ASP, GLU, CYS, TYR, C-)
    # are protonated when pH < pKa; basic residues (HIS, LYS, ARG, N+)
    # are protonated when pH < pKa
    protonated = []
    deprotonated = []
    unusual = []

    for r in results:
        is_protonated = ph < r["pka"]
        res_label = f"{r['residue']} {r['chain']}{r['number']}"
        entry = {
            "residue": r["residue"],
            "chain": r["chain"],
            "number": r["number"],
            "pka": r["pka"],
            "protonated": is_protonated,
        }

        if is_protonated:
            protonated.append(entry)
        else:
            deprotonated.append(entry)

        # Flag unusual protonation states
        if r["residue"] in ("ASP", "GLU") and is_protonated and ph > 5.0:
            entry["note"] = "Unusually protonated at this pH — may be catalytically important"
            unusual.append(entry)
        elif r["residue"] == "HIS":
            if abs(r["pka"] - ph) < 1.0:
                entry["note"] = "Near titration point — may switch protonation states"
                unusual.append(entry)
        elif r["residue"] == "CYS" and not is_protonated and ph < 8.0:
            entry["note"] = "Deprotonated CYS (thiolate) — possible catalytic or metal-binding role"
            unusual.append(entry)
        elif r["residue"] == "LYS" and not is_protonated:
            entry["note"] = "Unusually deprotonated LYS — may be in buried/hydrophobic environment"
            unusual.append(entry)

    return json.dumps({
        "status": "success",
        "pdb_id": pdb_id,
        "ph": ph,
        "total_residues": len(results),
        "protonated_count": len(protonated),
        "deprotonated_count": len(deprotonated),
        "unusual_states": unusual,
        "protonated": protonated,
        "deprotonated": deprotonated,
        "note": f"At pH {ph}: residues with pKa > {ph} are protonated, "
                f"pKa < {ph} are deprotonated.",
    }, indent=2)


# ============================================================
# Tool 14: Add Hydrogens (PDB2PQR)
# ============================================================

@mcp.tool()
def add_hydrogens(
    pdb_id: str,
    ph: float = 7.0,
    force_field: str = "AMBER",
) -> str:
    """
    Add hydrogen atoms to a protein structure using PDB2PQR.

    Uses PROPKA to determine protonation states at the given pH,
    then places hydrogens at chemically correct positions.
    The result is a new structure with all hydrogens added.

    Args:
        pdb_id: PDB ID or modified structure ID (e.g., "1HPX", "1YOG_ZN")
        ph: pH value for protonation state assignment (default 7.0)
        force_field: Force field for atom naming — "AMBER", "CHARMM", "PARSE", or "SWANSON" (default "AMBER")
    """
    key = pdb_id
    if key not in _structures:
        key = pdb_id.upper()
    if key not in _structures:
        try:
            key = _ensure_downloaded(pdb_id)
        except Exception:
            return json.dumps({"error": f"Could not load {pdb_id}"})

    pdb_text = _structures[key]

    try:
        from pdb2pqr.main import main_driver, build_main_parser
    except ImportError:
        return json.dumps({"error": "PDB2PQR is not installed. Install with: pip install pdb2pqr"})

    ff = force_field.upper()
    if ff not in ("AMBER", "CHARMM", "PARSE", "SWANSON"):
        return json.dumps({"error": f"Unknown force field '{force_field}'. Use AMBER, CHARMM, PARSE, or SWANSON."})

    # Write input PDB to temp file
    in_file = tempfile.NamedTemporaryFile(
        mode="w", suffix=".pdb", delete=False, dir=tempfile.gettempdir()
    )
    in_file.write(pdb_text)
    in_file.close()

    out_pqr = in_file.name.replace(".pdb", ".pqr")
    out_pdb = in_file.name.replace(".pdb", "_H.pdb")

    try:
        parser = build_main_parser()
        args = parser.parse_args([
            "--ff", ff,
            "--ffout", ff,
            "--with-ph", str(ph),
            "--titration-state-method", "propka",
            "--pdb-output", out_pdb,
            in_file.name,
            out_pqr,
        ])
        main_driver(args)

        if not os.path.exists(out_pdb):
            return json.dumps({"error": "PDB2PQR ran but did not produce output PDB."})

        with open(out_pdb) as f:
            h_pdb_text = f.read()

        # Count atoms and hydrogens
        total_atoms = 0
        h_count = 0
        for line in h_pdb_text.splitlines():
            if line.startswith(("ATOM", "HETATM")):
                total_atoms += 1
                if len(line) > 77 and line[76:78].strip() == "H":
                    h_count += 1

        # Store the protonated structure
        new_key = f"{key}_pH{ph}"
        _structures[new_key] = h_pdb_text

        return json.dumps({
            "status": "success",
            "new_id": new_key,
            "ph": ph,
            "force_field": ff,
            "total_atoms": total_atoms,
            "hydrogens_added": h_count,
            "note": f"Structure protonated at pH {ph} using {ff} force field. "
                    f"{h_count} hydrogen atoms added. Use get_modified_structure "
                    f"to retrieve the full PDB with hydrogens.",
        }, indent=2)

    except Exception as e:
        return json.dumps({"error": f"PDB2PQR failed: {e}"})
    finally:
        for path in [in_file.name, out_pqr, out_pdb]:
            if os.path.exists(path):
                os.unlink(path)


# ============================================================
# Resources (data the AI can read, like URLs)
# ============================================================

@mcp.resource("pdb://structure/{pdb_id}")
def get_structure_resource(pdb_id: str) -> str:
    """Complete structure information for a PDB ID."""
    response = requests.get(
        f"{PDB_DATA_API}/core/entry/{pdb_id.lower()}",
        headers=HEADERS,
        timeout=30,
    )
    response.raise_for_status()
    return json.dumps(response.json(), indent=2)


@mcp.resource("pdb://coordinates/{pdb_id}")
def get_coordinates_resource(pdb_id: str) -> str:
    """Structure coordinates in PDB format."""
    response = requests.get(
        f"{PDB_FILES_URL}/{pdb_id.lower()}.pdb",
        timeout=30,
    )
    response.raise_for_status()
    return response.text


@mcp.resource("pdb://mmcif/{pdb_id}")
def get_mmcif_resource(pdb_id: str) -> str:
    """Structure data in mmCIF format."""
    response = requests.get(
        f"{PDB_FILES_URL}/{pdb_id.lower()}.cif",
        timeout=30,
    )
    response.raise_for_status()
    return response.text


# ============================================================
# Prompts (reusable templates for the AI)
# ============================================================

@mcp.prompt()
def analyze_structure(pdb_id: str) -> str:
    """Prompt to analyze a protein structure comprehensively."""
    return f"""Please analyze the protein structure with PDB ID {pdb_id}.
    
Use the available tools to:
1. Get the structure info (get_structure_info)
2. Check the quality metrics (get_structure_quality)
3. Search for related structures by UniProt ID if available

Provide a summary including:
- What protein/complex this is
- Experimental method and resolution
- Quality assessment
- Any notable features or ligands"""


@mcp.prompt()
def compare_methods(protein_name: str) -> str:
    """Prompt to compare X-ray and cryoEM structures of the same protein."""
    return f"""Search for structures of {protein_name} solved by both X-RAY DIFFRACTION 
and ELECTRON MICROSCOPY. Compare the available structures in terms of:
- Resolution
- Quality metrics
- What biological state they capture

Use search_structures with experimental_method filter for each method."""


# ============================================================
# Run the server
# ============================================================

if __name__ == "__main__":
    mcp.run()
