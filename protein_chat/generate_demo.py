#!/usr/bin/env python3
"""
Generate demo conversation data for ProteinChat AI.

Downloads 6M8F, runs sequential modifications, and saves all PDB versions
plus the chat history to a JSON file that the app loads on startup.

Usage:
    python generate_demo.py
"""

import json
import os
import sys

# Add parent dir so we can import pdb_mcp_server functions directly
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pdb_mcp_server import (
    _ensure_downloaded,
    _structures,
    remove_hetatm,
    list_hetatm,
)


def main():
    print("Generating demo data for 6M8F...")

    # Step 1: Download 6M8F
    print("  Downloading 6M8F...")
    key = _ensure_downloaded("6M8F")
    original_pdb = _structures[key]
    print(f"  Downloaded: {len(original_pdb.splitlines())} lines")

    # Step 2: Remove SO4
    print("  Removing SO4...")
    result = json.loads(remove_hetatm("6M8F", residue_names=["SO4"]))
    step2_id = result["new_id"]
    step2_pdb = _structures[step2_id]
    print(f"  {step2_id}: removed {result['total_atoms_removed']} atoms")

    # Step 3: Remove FRU
    print("  Removing FRU...")
    result = json.loads(remove_hetatm(step2_id, residue_names=["FRU"]))
    step3_id = result["new_id"]
    step3_pdb = _structures[step3_id]
    print(f"  {step3_id}: removed {result['total_atoms_removed']} atoms")

    # Step 4: Remove GLC
    print("  Removing GLC...")
    result = json.loads(remove_hetatm(step3_id, residue_names=["GLC"]))
    step4_id = result["new_id"]
    step4_pdb = _structures[step4_id]
    print(f"  {step4_id}: removed {result['total_atoms_removed']} atoms")

    # Step 5: Remove water (HOH)
    print("  Removing water (HOH)...")
    result = json.loads(remove_hetatm(step4_id, remove_water=True))
    step5_id = result["new_id"]
    step5_pdb = _structures[step5_id]
    print(f"  {step5_id}: removed {result['total_atoms_removed']} atoms")

    # Build demo data
    demo = {
        "title": "Visualize 6M8F",
        "chat_history": [
            {"role": "user", "content": "Visualize PDB 6M8F"},
            {
                "role": "assistant",
                "content": (
                    "**6M8F: Engineered Sperm Whale Myoglobin-Based Carbene Transferase**\n\n"
                    "This is an ultra-high resolution structure (1.1 \u00c5!) of an engineered myoglobin "
                    "that catalyzes stereoselective cyclopropanation reactions. It contains a heme cofactor "
                    "and was solved by X-ray diffraction at CHESS synchrotron. Published in *ACS Catalysis* (2019)."
                ),
                "structure_ids": ["6M8F"],
            },
            {"role": "user", "content": "Remove SO4"},
            {
                "role": "assistant",
                "content": (
                    "Done! I've removed **15 sulfate ions (SO4)** from the structure. "
                    "The modified structure now shows just the protein and heme cofactor "
                    "without the crystallization artifacts."
                ),
                "structure_ids": [step2_id],
            },
            {"role": "user", "content": "Remove FRU"},
            {
                "role": "assistant",
                "content": (
                    "Removed **23 FRU (fructose)** residues. The structure is now cleaner \u2014 "
                    "showing only the myoglobin protein and its essential heme cofactor."
                ),
                "structure_ids": [step3_id],
            },
            {"role": "user", "content": "Is there any non-protein residue in this PDB?"},
            {
                "role": "assistant",
                "content": (
                    "Yes! The structure still contains:\n\n"
                    "- **HEM** (heme cofactor) \u2014 1 instance in chain A, the essential iron porphyrin active site\n"
                    "- **GLC** (glucose) \u2014 1 instance in chain B, a sugar molecule from crystallization\n"
                    "- **HOH** (water) \u2014 224 molecules, crystallographic waters\n\n"
                    "The heme is critical for function, but you could remove the glucose and/or water if desired."
                ),
                "structure_ids": [],
            },
            {"role": "user", "content": "Remove GLC"},
            {
                "role": "assistant",
                "content": (
                    "Done! Removed **22 glucose atoms**. The structure now contains only "
                    "the myoglobin protein, its essential heme cofactor, and 224 water molecules."
                ),
                "structure_ids": [step4_id],
            },
            {"role": "user", "content": "Remove water"},
            {
                "role": "assistant",
                "content": (
                    "Removed all **224 water molecules (HOH)**. The structure is now fully clean \u2014 "
                    "just the myoglobin protein and its heme cofactor, ready for analysis!"
                ),
                "structure_ids": [step5_id],
            },
        ],
        "pdb_cache": {
            "6M8F": original_pdb,
            step2_id: step2_pdb,
            step3_id: step3_pdb,
            step4_id: step4_pdb,
            step5_id: step5_pdb,
        },
        "modification_history": [
            {"id": "6M8F", "label": "Original: 6M8F"},
            {"id": step2_id, "label": "Removed SO4"},
            {"id": step3_id, "label": "Removed FRU"},
            {"id": step4_id, "label": "Removed GLC"},
            {"id": step5_id, "label": "Removed HOH, WAT, DOD"},
        ],
        "current_structure_id": step5_id,
    }

    # Save to JSON
    out_path = os.path.join(os.path.dirname(__file__), "demo_conversation.json")
    with open(out_path, "w") as f:
        json.dump(demo, f)

    size_mb = os.path.getsize(out_path) / (1024 * 1024)
    print(f"\nSaved to {out_path} ({size_mb:.1f} MB)")
    print(f"PDB versions: {list(demo['pdb_cache'].keys())}")
    print("Done!")


if __name__ == "__main__":
    main()
