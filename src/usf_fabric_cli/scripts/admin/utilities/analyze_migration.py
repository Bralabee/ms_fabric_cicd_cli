#!/usr/bin/env python3
"""
Migration helper - analyze existing custom Fabric solutions and suggest migration paths.
"""

import argparse
import ast
import json
from pathlib import Path
from typing import Any, Dict


class CustomSolutionAnalyzer:
    """Analyze existing custom Fabric solutions."""

    def __init__(self, source_directory: str):
        self.source_dir = Path(source_directory)
        self.analysis: Dict[str, Any] = {
            "total_files": 0,
            "total_loc": 0,
            "components_found": [],
            "fabric_api_calls": [],
            "cli_replaceable": [],
            "custom_logic_needed": [],
            "migration_complexity": "Unknown",
        }

    def analyze(self) -> Dict[str, Any]:
        """Perform analysis of custom solution."""
        print(f"🔍 Analyzing custom solution in {self.source_dir}")

        python_files = list(self.source_dir.rglob("*.py"))
        self.analysis["total_files"] = len(python_files)

        for py_file in python_files:
            self._analyze_file(py_file)

        self._determine_migration_complexity()
        self._generate_recommendations()

        return self.analysis

    def _analyze_file(self, file_path: Path) -> None:
        """Analyze individual Python file."""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()

            lines = content.split("\n")
            loc = len(
                [
                    line
                    for line in lines
                    if line.strip() and not line.strip().startswith("#")
                ]
            )
            self.analysis["total_loc"] += loc

            try:
                tree = ast.parse(content)
                self._analyze_ast(tree, file_path)
            except SyntaxError:
                print(f"⚠️  Could not parse {file_path} (syntax error)")

        except Exception as e:
            print(f"⚠️  Error analyzing {file_path}: {e}")

    def _analyze_ast(self, tree: ast.AST, file_path: Path) -> None:
        """Analyze AST for Fabric-related patterns."""
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                self._analyze_function(node, file_path)
            elif isinstance(node, ast.Call):
                self._analyze_call(node, file_path)

    def _analyze_function(self, node: ast.FunctionDef, file_path: Path) -> None:
        """Analyze function definitions."""
        func_name = node.name.lower()

        fabric_patterns = [
            "workspace",
            "lakehouse",
            "warehouse",
            "notebook",
            "pipeline",
            "folder",
            "item",
            "git",
            "capacity",
            "principal",
        ]

        for pattern in fabric_patterns:
            if pattern in func_name:
                component = {
                    "type": "function",
                    "name": node.name,
                    "file": str(file_path.relative_to(self.source_dir)),
                    "pattern": pattern,
                    "cli_replaceable": self._is_cli_replaceable(pattern),
                }
                self.analysis["components_found"].append(component)
                break

    def _analyze_call(self, node: ast.Call, file_path: Path) -> None:
        """Analyze function/method calls."""
        if isinstance(node.func, ast.Attribute):
            method_name = node.func.attr.lower()

            if method_name in ["post", "get", "put", "patch", "delete"]:
                if hasattr(node, "args") and len(node.args) > 0:
                    if isinstance(node.args[0], ast.Constant):
                        url = node.args[0].value
                        if isinstance(url, str) and "fabric" in url.lower():
                            api_call = {
                                "method": method_name.upper(),
                                "file": str(file_path.relative_to(self.source_dir)),
                                "likely_fabric_api": True,
                            }
                            self.analysis["fabric_api_calls"].append(api_call)

    def _is_cli_replaceable(self, pattern: str) -> bool:
        """Determine if pattern can be replaced with Fabric CLI."""
        cli_supported = [
            "workspace",
            "lakehouse",
            "warehouse",
            "notebook",
            "folder",
            "item",
            "git",
        ]
        return pattern in cli_supported

    def _determine_migration_complexity(self) -> None:
        """Determine overall migration complexity."""
        total_loc = self.analysis["total_loc"]
        cli_replaceable_count = len(
            [c for c in self.analysis["components_found"] if c["cli_replaceable"]]
        )
        total_components = len(self.analysis["components_found"])

        if total_loc < 500:
            complexity = "LOW"
        elif total_loc < 1500:
            complexity = "MEDIUM"
        else:
            complexity = "HIGH"

        if total_components > 0:
            cli_percentage = (cli_replaceable_count / total_components) * 100
            if cli_percentage > 80:
                complexity = f"{complexity} (High CLI compatibility)"
            elif cli_percentage > 50:
                complexity = f"{complexity} (Medium CLI compatibility)"
            else:
                complexity = f"{complexity} (Low CLI compatibility)"

        self.analysis["migration_complexity"] = complexity

    def _generate_recommendations(self) -> None:
        """Generate migration recommendations."""
        total_loc = self.analysis["total_loc"]
        cli_replaceable = [
            c for c in self.analysis["components_found"] if c["cli_replaceable"]
        ]

        recommendations = []

        if total_loc > 1000:
            recommendations.append(
                {
                    "priority": "HIGH",
                    "action": "Consider migration to thin wrapper approach",
                    "reason": (
                        f"Large codebase ({total_loc} LOC)"
                        " has high maintenance burden"
                    ),
                    "target_reduction": (
                        "Potential reduction to ~270 LOC"
                        " (85% reduction)"
                    ),
                }
            )

        if len(cli_replaceable) > 0:
            recommendations.append(
                {
                    "priority": "MEDIUM",
                    "action": (
                        f"Replace {len(cli_replaceable)}"
                        " components with Fabric CLI"
                    ),
                    "reason": "These components have direct CLI equivalents",
                    "components": [c["name"] for c in cli_replaceable],
                }
            )

        if len(self.analysis["fabric_api_calls"]) > 10:
            recommendations.append(
                {
                    "priority": "MEDIUM",
                    "action": "Replace direct API calls with CLI commands",
                    "reason": (
                        f"Found {len(self.analysis['fabric_api_calls'])}"
                        " direct API calls"
                    ),
                    "benefit": "Better error handling and Microsoft support",
                }
            )

        self.analysis["recommendations"] = recommendations

    def generate_report(self, output_file: str = None) -> Dict[str, Any]:
        """Generate migration analysis report."""
        report = {
            "analysis_summary": {
                "total_files": self.analysis["total_files"],
                "total_loc": self.analysis["total_loc"],
                "migration_complexity": self.analysis["migration_complexity"],
                "components_found": len(self.analysis["components_found"]),
                "cli_replaceable": len(
                    [
                        c
                        for c in self.analysis["components_found"]
                        if c["cli_replaceable"]
                    ]
                ),
                "fabric_api_calls": len(self.analysis["fabric_api_calls"]),
            },
            "detailed_analysis": self.analysis,
            "migration_steps": [
                "1. Setup new thin wrapper project structure",
                "2. Identify components that can use Fabric CLI directly",
                "3. Migrate configuration to YAML-based approach",
                "4. Implement thin wrapper for remaining custom logic",
                "5. Create tests and validation",
                "6. Gradual rollout and validation",
            ],
        }

        if output_file:
            with open(output_file, "w") as f:
                json.dump(report, f, indent=2)
            print(f"📄 Migration report saved to {output_file}")

        return report


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Analyze custom Fabric solution for migration"
    )
    parser.add_argument("source_directory", help="Path to existing custom solution")
    parser.add_argument("--output", help="Output file for detailed report (JSON)")

    args = parser.parse_args()

    if not Path(args.source_directory).exists():
        print(f"❌ Directory not found: {args.source_directory}")
        return 1

    try:
        analyzer = CustomSolutionAnalyzer(args.source_directory)
        analysis = analyzer.analyze()

        print("\n📊 Migration Analysis Summary:")
        print(f"   Total files: {analysis['total_files']}")
        print(f"   Total LOC: {analysis['total_loc']}")
        print(f"   Components found: {len(analysis['components_found'])}")
        print(
            "   CLI replaceable:"
            f" {len([c for c in analysis['components_found'] if c['cli_replaceable']])}"
        )
        print(f"   Migration complexity: {analysis['migration_complexity']}")

        if "recommendations" in analysis:
            print("\n💡 Recommendations:")
            for rec in analysis["recommendations"]:
                print(f"   {rec['priority']}: {rec['action']}")
                print(f"      Reason: {rec['reason']}")

        if args.output:
            analyzer.generate_report(args.output)

    except Exception as e:
        print(f"❌ Analysis failed: {e}")
        return 1

    return 0


if __name__ == "__main__":
    exit(main())
