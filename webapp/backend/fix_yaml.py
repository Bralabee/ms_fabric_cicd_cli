#!/usr/bin/env python3
"""Fix YAML syntax issues in scenario files.

Issues to fix:
1. Lines like `- **text**` - the ** is interpreted as YAML alias
2. Lines like `- `text`` - backtick cannot start a token

Solution: Quote these strings with double quotes.
"""
import os
import re

scenarios_dir = 'app/content/scenarios'

def fix_yaml_line(line):
    """Fix a single line if it has problematic patterns."""
    # Pattern: starts with spaces, dash, space, then content
    # If the content contains backticks or starts with **, we need to quote it
    
    # Match: "      - something" where something needs quoting
    match = re.match(r'^(\s*- )(.+)$', line)
    if match:
        indent = match.group(1)
        value = match.group(2).rstrip()
        
        # Already quoted? Skip
        if value.startswith('"') and value.endswith('"'):
            return line
        if value.startswith("'") and value.endswith("'"):
            return line
        
        # Needs quoting if:
        # 1. Starts with ` or *
        # 2. Contains unquoted backticks
        needs_quote = False
        if value.startswith('`') or value.startswith('*'):
            needs_quote = True
        elif '`' in value:
            needs_quote = True
        
        if needs_quote:
            # Wrap in double quotes, escaping any existing double quotes
            escaped_value = value.replace('"', '\\"')
            return f'{indent}"{escaped_value}"\n'
    
    return line

def process_file(filepath):
    """Process a single YAML file."""
    with open(filepath, 'r') as f:
        lines = f.readlines()
    
    changes = 0
    new_lines = []
    for i, line in enumerate(lines):
        new_line = fix_yaml_line(line)
        if new_line != line:
            print(f"  Line {i+1}: {line.rstrip()[:60]}")
            print(f"       ->: {new_line.rstrip()[:60]}")
            changes += 1
        new_lines.append(new_line)
    
    if changes > 0:
        with open(filepath, 'w') as f:
            f.writelines(new_lines)
        print(f"  Fixed {changes} lines")
    
    return changes

def main():
    total_changes = 0
    for filename in sorted(os.listdir(scenarios_dir)):
        if filename.endswith('.yaml'):
            filepath = os.path.join(scenarios_dir, filename)
            print(f"\nProcessing {filename}:")
            changes = process_file(filepath)
            total_changes += changes
            if changes == 0:
                print("  No changes needed")
    
    print(f"\n\nTotal changes: {total_changes}")

if __name__ == '__main__':
    main()
