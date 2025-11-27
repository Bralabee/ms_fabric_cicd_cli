#!/usr/bin/env python3
"""
Bulk destroy workspaces from a list file.
"""

import argparse
import sys
import os
import time
from pathlib import Path

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

from core.fabric_wrapper import FabricCLIWrapper
from core.config import get_environment_variables

def parse_workspace_list(file_path):
    workspaces = []
    with open(file_path, 'r') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#') or line.startswith('Name'):
                continue
            
            # Extract first column (Name)
            parts = line.split()
            name_part = parts[0]
            
            # Clean up name
            if name_part.endswith('.Workspace'):
                name = name_part[:-10] # Remove .Workspace
            else:
                name = name_part
                
            workspaces.append(name)
    return workspaces

def bulk_destroy(file_path, dry_run=False, force=False):
    workspaces = parse_workspace_list(file_path)
    
    if not workspaces:
        print("No workspaces found in file.")
        return

    print(f"Found {len(workspaces)} workspaces to delete:")
    for ws in workspaces:
        print(f"  - {ws}")
    
    if dry_run:
        print("\n[Dry Run] No actions taken.")
        return

    if not force:
        confirm = input("\nAre you sure you want to delete these workspaces? (yes/no): ")
        if confirm.lower() != 'yes':
            print("Operation cancelled.")
            return

    # Initialize wrapper
    try:
        env_vars = get_environment_variables()
        fabric = FabricCLIWrapper(env_vars.get('FABRIC_TOKEN', ''))
    except Exception as e:
        print(f"Error initializing Fabric wrapper: {e}")
        return
    
    print("\nStarting deletion...")
    success_count = 0
    fail_count = 0
    
    for ws in workspaces:
        print(f"Deleting {ws}...", end='', flush=True)
        try:
            result = fabric.delete_workspace(ws)
            if result['success']:
                print(" ✅ Deleted")
                success_count += 1
            else:
                print(f" ❌ Failed: {result.get('error')}")
                fail_count += 1
        except Exception as e:
            print(f" ❌ Error: {e}")
            fail_count += 1
            
    print(f"\nSummary: {success_count} deleted, {fail_count} failed.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Bulk destroy workspaces")
    parser.add_argument("file", help="Path to file containing workspace list")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be deleted without doing it")
    parser.add_argument("--force", action="store_true", help="Skip confirmation")
    
    args = parser.parse_args()
    
    if not Path(args.file).exists():
        print(f"Error: File {args.file} not found")
        sys.exit(1)
        
    bulk_destroy(args.file, args.dry_run, args.force)
