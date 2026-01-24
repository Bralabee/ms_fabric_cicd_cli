"""
Jinja2-based artifact templating for environment-specific deployments.

Enables dynamic variable substitution in Fabric artifacts including notebooks,
lakehouse definitions, pipelines, and data flows. Supports environment-specific
configurations for connection strings, capacity IDs, and data source paths.

Sandboxed execution prevents arbitrary code execution in templates.
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional, Union

from jinja2 import (
    FileSystemLoader,
    StrictUndefined,
    TemplateSyntaxError,
    UndefinedError,
    sandbox,
)

logger = logging.getLogger(__name__)


class ArtifactTemplateEngine:
    """
    Sandboxed Jinja2 template engine for Microsoft Fabric artifacts.

    Provides environment-specific variable substitution with strict undefined
    variable handling to prevent deployment errors.
    """

    def __init__(
        self,
        template_dirs: Optional[list[Union[str, Path]]] = None,
        strict_mode: bool = True,
    ):
        """
        Initializes sandboxed Jinja2 environment.

        Args:
            template_dirs: Template file search directories
            strict_mode: Raises error on undefined variables when True
        """
        self.strict_mode = strict_mode

        # Setup Jinja2 environment with sandboxing for security
        if template_dirs:
            loader = FileSystemLoader([str(d) for d in template_dirs])
            self.env = sandbox.SandboxedEnvironment(
                loader=loader,
                undefined=StrictUndefined if strict_mode else None,
                autoescape=False,  # We're working with code/config, not HTML
            )
        else:
            self.env = sandbox.SandboxedEnvironment(
                undefined=StrictUndefined if strict_mode else None, autoescape=False
            )

        # Add custom filters
        self.env.filters["jsonify"] = json.dumps
        self.env.filters["upper"] = str.upper
        self.env.filters["lower"] = str.lower

    def render_string(
        self,
        template_string: str,
        variables: Dict[str, Any],
        validate_only: bool = False,
    ) -> Union[str, bool]:
        """
        Render a template string with variables.

        Args:
            template_string: Jinja2 template string
            variables: Dictionary of variables to inject
            validate_only: Only validate syntax, don't render

        Returns:
            Rendered string or validation result
        """
        try:
            template = self.env.from_string(template_string)

            if validate_only:
                # Just validate syntax
                return True

            rendered = template.render(**variables)
            return rendered

        except TemplateSyntaxError as e:
            logger.error(f"Template syntax error: {e}")
            if validate_only:
                return False
            raise ValueError(f"Template syntax error at line {e.lineno}: {e.message}")

        except UndefinedError as e:
            logger.error(f"Undefined variable in template: {e}")
            raise ValueError(f"Undefined variable in template: {e}")

        except Exception as e:
            logger.error(f"Template rendering error: {e}")
            raise ValueError(f"Template rendering error: {e}")

    def render_file(
        self,
        template_path: Path,
        variables: Dict[str, Any],
        output_path: Optional[Path] = None,
    ) -> str:
        """
        Render a template file with variables.

        Args:
            template_path: Path to template file
            variables: Dictionary of variables to inject
            output_path: Optional path to write rendered output

        Returns:
            Rendered content
        """
        if not template_path.exists():
            raise FileNotFoundError(f"Template file not found: {template_path}")

        # Read template
        with open(template_path, "r", encoding="utf-8") as f:
            template_string = f.read()

        # Render
        rendered = self.render_string(template_string, variables)

        # Write to output file if specified
        if output_path:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(rendered)
            logger.info(f"Rendered template to: {output_path}")

        return rendered

    def render_json(
        self, json_template: Union[str, Dict], variables: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Render a JSON template (for Fabric artifacts like notebooks, pipelines).

        This is useful for transforming JSON-based Fabric artifacts before deployment.

        Args:
            json_template: JSON string or dict containing Jinja2 templates
            variables: Dictionary of variables to inject

        Returns:
            Rendered JSON as dictionary
        """
        # Convert to string if dict
        if isinstance(json_template, dict):
            template_string = json.dumps(json_template, indent=2)
        else:
            template_string = json_template

        # Render
        rendered_string = self.render_string(template_string, variables)

        # Parse back to JSON
        try:
            return json.loads(rendered_string)
        except json.JSONDecodeError as e:
            logger.error(f"Rendered template is not valid JSON: {e}")
            raise ValueError(f"Rendered template is not valid JSON: {e}")

    def prepare_environment_variables(
        self,
        environment: str,
        base_vars: Dict[str, Any],
        env_specific_vars: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Prepare variables for a specific environment with smart merging.

        Args:
            environment: Target environment (dev/staging/prod)
            base_vars: Base variables available in all environments
            env_specific_vars: Environment-specific overrides

        Returns:
            Merged variable dictionary
        """
        # Start with base vars
        final_vars = base_vars.copy()

        # Add environment name
        final_vars["environment"] = environment
        final_vars["env"] = environment

        # Add environment-specific overrides
        if env_specific_vars:
            final_vars.update(env_specific_vars)

        logger.debug(
            f"Prepared {len(final_vars)} variables for environment: {environment}"
        )
        return final_vars

    @staticmethod
    def extract_template_variables(template_string: str) -> list[str]:
        """
        Extract variable names from a template string.

        Useful for validation and documentation.

        Args:
            template_string: Jinja2 template string

        Returns:
            List of variable names found in template
        """
        import re

        # Match Jinja2 variable syntax: {{ variable_name }}
        pattern = r"\{\{\s*([a-zA-Z_][a-zA-Z0-9_\.]*)\s*\}\}"
        matches = re.findall(pattern, template_string)

        # Remove duplicates and sort
        unique_vars = sorted(set(matches))
        return unique_vars


class FabricArtifactTemplater:
    """
    High-level templating for Fabric-specific artifacts.

    Provides convenience methods for common Fabric artifact types.
    """

    def __init__(self, template_engine: Optional[ArtifactTemplateEngine] = None):
        """
        Initialize Fabric artifact templater.

        Args:
            template_engine: Optional custom template engine
        """
        self.engine = template_engine or ArtifactTemplateEngine()

    def render_notebook(
        self, notebook_path: Path, variables: Dict[str, Any], output_path: Path
    ) -> Dict[str, Any]:
        """
        Render a Fabric Notebook with environment-specific values.

        Notebooks are JSON files with embedded code cells.

        Args:
            notebook_path: Path to notebook template
            variables: Variables to inject
            output_path: Where to save rendered notebook

        Returns:
            Rendered notebook as dict
        """
        logger.info(f"Rendering notebook: {notebook_path}")

        # Read notebook
        with open(notebook_path, "r", encoding="utf-8") as f:
            notebook_template = json.load(f)

        # Render
        rendered_notebook = self.engine.render_json(notebook_template, variables)

        # Write output
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(rendered_notebook, f, indent=2)

        logger.info(f"Rendered notebook saved to: {output_path}")
        return rendered_notebook

    def render_lakehouse_definition(
        self, definition_path: Path, variables: Dict[str, Any], output_path: Path
    ) -> Dict[str, Any]:
        """
        Render a Lakehouse definition with environment-specific values.

        Args:
            definition_path: Path to lakehouse definition template
            variables: Variables to inject
            output_path: Where to save rendered definition

        Returns:
            Rendered definition as dict
        """
        logger.info(f"Rendering lakehouse definition: {definition_path}")

        # Read definition
        with open(definition_path, "r", encoding="utf-8") as f:
            definition_template = json.load(f)

        # Render
        rendered_definition = self.engine.render_json(definition_template, variables)

        # Write output
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(rendered_definition, f, indent=2)

        logger.info(f"Rendered lakehouse definition saved to: {output_path}")
        return rendered_definition

    def render_pipeline(
        self, pipeline_path: Path, variables: Dict[str, Any], output_path: Path
    ) -> Dict[str, Any]:
        """
        Render a Data Pipeline definition with environment-specific values.

        Args:
            pipeline_path: Path to pipeline template
            variables: Variables to inject
            output_path: Where to save rendered pipeline

        Returns:
            Rendered pipeline as dict
        """
        logger.info(f"Rendering pipeline: {pipeline_path}")

        # Read pipeline
        with open(pipeline_path, "r", encoding="utf-8") as f:
            pipeline_template = json.load(f)

        # Render
        rendered_pipeline = self.engine.render_json(pipeline_template, variables)

        # Write output
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(rendered_pipeline, f, indent=2)

        logger.info(f"Rendered pipeline saved to: {output_path}")
        return rendered_pipeline

    def validate_artifact_template(
        self, artifact_path: Path, required_variables: Optional[list[str]] = None
    ) -> tuple[bool, list[str]]:
        """
        Validate an artifact template for correctness.

        Args:
            artifact_path: Path to artifact template
            required_variables: Optional list of variables that must be present

        Returns:
            (is_valid, list_of_errors)
        """
        errors = []

        # Check file exists
        if not artifact_path.exists():
            errors.append(f"Template file not found: {artifact_path}")
            return False, errors

        # Read template
        try:
            with open(artifact_path, "r", encoding="utf-8") as f:
                content = f.read()
        except Exception as e:
            errors.append(f"Could not read template: {e}")
            return False, errors

        # Extract variables
        found_variables = ArtifactTemplateEngine.extract_template_variables(content)

        # Check required variables
        if required_variables:
            missing = set(required_variables) - set(found_variables)
            if missing:
                errors.append(f"Missing required variables: {missing}")

        # Try to validate syntax (with dummy values)
        dummy_vars = {var: f"<{var}>" for var in found_variables}
        try:
            result = self.engine.render_string(content, dummy_vars, validate_only=True)
            if result is False:
                errors.append("Template syntax error: invalid template syntax")
        except Exception as e:
            errors.append(f"Template syntax error: {e}")

        is_valid = len(errors) == 0
        return is_valid, errors
