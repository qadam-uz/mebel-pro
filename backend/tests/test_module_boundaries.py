"""Architecture regression tests for the backend module layout."""

from __future__ import annotations

import ast
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
APP_ROOT = BACKEND_ROOT / "app"
MODULES_ROOT = APP_ROOT / "modules"
ROUTES_ROOT = APP_ROOT / "api" / "routes"
MODELS_ROOT = APP_ROOT / "models"
SCHEMAS_ROOT = APP_ROOT / "schemas"
SERVICES_ROOT = APP_ROOT / "services"

MIGRATED_MODULES = {
    "access",
    "catalog",
    "client_portal",
    "cutting",
    "finance",
    "inventory",
    "platform",
    "sales",
    "support",
    "workshop",
}

LEGACY_SERVICE_PREFIX = "app.services."
LEGACY_SCHEMA_PREFIX = "app.schemas."
LEGACY_MODEL_PREFIX = "app.models."
PUBLIC_MODULE_FILES = {"api", "contracts", "schemas"}

MODULE_ROUTE_FILES = {
    "access": {"routes.py"},
    "catalog": {"routes.py"},
    "client_portal": {"public_routes.py", "routes.py"},
    "cutting": {"routes.py"},
    "finance": {"routes.py"},
    "inventory": {"invoice_routes.py", "routes.py"},
    "platform": {"routes.py"},
    "sales": {"routes.py"},
    "support": {"files_routes.py", "notifications_routes.py"},
    "workshop": {"routes.py", "setup_routes.py"},
}

MODULE_SCHEMA_FILES = {
    "access": {"schemas.py"},
    "catalog": {"schemas.py"},
    "client_portal": {"schemas.py"},
    "cutting": {"schemas.py"},
    "finance": {"schemas.py"},
    "inventory": {"schemas.py"},
    "platform": {"schemas.py"},
    "sales": {"schemas.py"},
    "support": {"files_schemas.py", "notifications_schemas.py"},
    "workshop": {"schemas.py"},
}

MODULE_MODEL_FILES = {
    "access": {"models.py"},
    "catalog": {"models.py"},
    "client_portal": {"models.py"},
    "cutting": {"models.py"},
    "finance": {"models.py"},
    "inventory": {"models.py"},
    "platform": {"models.py"},
    "sales": {"models.py"},
    "support": {"models.py"},
    "workshop": {"models.py"},
}

API_ROUTE_ALLOWLIST = {"__init__.py", "health.py"}
MODEL_ALLOWLIST = {"__init__.py", "base.py", "enums.py"}
SCHEMA_ALLOWLIST = {"__init__.py", "common.py"}
SERVICE_ALLOWLIST = {"__init__.py"}
LEGACY_SCHEMA_ALLOWLIST = {"app.schemas.common"}
LEGACY_MODEL_ALLOWLIST = {"app.models.base", "app.models.enums"}


def test_backend_modules_have_public_api_and_contract_files() -> None:
    assert {
        path.name
        for path in MODULES_ROOT.iterdir()
        if path.is_dir() and not path.name.startswith("__")
    } == MIGRATED_MODULES
    for module_name in MIGRATED_MODULES:
        module_root = MODULES_ROOT / module_name
        assert (module_root / "__init__.py").exists()
        assert (module_root / "api.py").exists()
        assert (module_root / "contracts.py").exists()


def test_domain_route_implementations_live_with_their_modules() -> None:
    assert {path.name for path in ROUTES_ROOT.glob("*.py")} <= API_ROUTE_ALLOWLIST

    for module_name, route_files in MODULE_ROUTE_FILES.items():
        module_root = MODULES_ROOT / module_name
        for route_file in route_files:
            assert (module_root / route_file).exists()


def test_domain_schema_implementations_live_with_their_modules() -> None:
    for module_name, schema_files in MODULE_SCHEMA_FILES.items():
        module_root = MODULES_ROOT / module_name
        for schema_file in schema_files:
            assert (module_root / schema_file).exists()


def test_domain_model_implementations_live_with_their_modules() -> None:
    for module_name, model_files in MODULE_MODEL_FILES.items():
        module_root = MODULES_ROOT / module_name
        for model_file in model_files:
            assert (module_root / model_file).exists()


def test_legacy_layer_first_domain_files_are_not_reintroduced() -> None:
    assert {path.name for path in MODELS_ROOT.glob("*.py")} <= MODEL_ALLOWLIST
    assert {path.name for path in SCHEMAS_ROOT.glob("*.py")} <= SCHEMA_ALLOWLIST
    assert {path.name for path in SERVICES_ROOT.glob("*.py")} <= SERVICE_ALLOWLIST


def test_production_code_uses_migrated_modules_through_public_apis() -> None:
    violations: list[str] = []
    for path in sorted(APP_ROOT.rglob("*.py")):
        if path.name in {"api.py", "contracts.py", "__init__.py"}:
            continue
        for imported_module, line_number in _imported_modules(path):
            if imported_module.startswith(LEGACY_SERVICE_PREFIX):
                violations.append(
                    f"{path.relative_to(BACKEND_ROOT)}:{line_number} imports {imported_module}"
                )
            if (
                imported_module.startswith(LEGACY_SCHEMA_PREFIX)
                and imported_module not in LEGACY_SCHEMA_ALLOWLIST
            ):
                violations.append(
                    f"{path.relative_to(BACKEND_ROOT)}:{line_number} imports {imported_module}"
                )
            if (
                imported_module.startswith(LEGACY_MODEL_PREFIX)
                and imported_module not in LEGACY_MODEL_ALLOWLIST
            ):
                violations.append(
                    f"{path.relative_to(BACKEND_ROOT)}:{line_number} imports {imported_module}"
                )
            if _is_private_cross_module_import(path, imported_module):
                violations.append(
                    f"{path.relative_to(BACKEND_ROOT)}:{line_number} imports {imported_module}"
                )
    assert violations == []


def _imported_modules(path: Path) -> list[tuple[str, int]]:
    tree = ast.parse(path.read_text(), filename=str(path))
    imports: list[tuple[str, int]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend((alias.name, node.lineno) for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            imports.append((node.module, node.lineno))
    return imports


def _is_private_cross_module_import(path: Path, imported_module: str) -> bool:
    parts = imported_module.split(".")
    if (
        len(parts) < 4
        or parts[0] != "app"
        or parts[1] != "modules"
        or parts[2] not in MIGRATED_MODULES
        or parts[3] in PUBLIC_MODULE_FILES
        or parts[3].endswith("_schemas")
    ):
        return False
    source_module = _source_module_name(path)
    return source_module != parts[2]


def _source_module_name(path: Path) -> str | None:
    try:
        relative = path.relative_to(MODULES_ROOT)
    except ValueError:
        return None
    return relative.parts[0] if relative.parts else None
