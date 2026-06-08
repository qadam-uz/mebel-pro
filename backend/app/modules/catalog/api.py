"""Public catalog API used by routes and other modules."""

from app.modules.catalog.contracts import Manufacturer, Material
from app.modules.catalog.schemas import MaterialResponse
from app.modules.catalog.service import (
    BranchCatalogOption,
    BranchMaterialRecord,
    MaterialRecord,
    add_branch_material,
    create_manufacturer,
    create_material,
    get_manufacturer,
    get_material,
    list_branch_catalog_options,
    list_branch_materials,
    list_manufacturers,
    list_materials,
    set_branch_material_status,
    set_manufacturer_status,
    set_material_status,
    update_branch_material,
    update_manufacturer,
    update_material,
)


def material_response_from_models(
    material: Material,
    manufacturer: Manufacturer,
) -> MaterialResponse:
    """Build the public material response shape from catalog-owned records."""

    return MaterialResponse(
        id=material.id,
        kind=material.kind,
        manufacturer_id=material.manufacturer_id,
        manufacturer_name=manufacturer.name,
        type=material.type,
        name=material.name,
        thickness_mm=material.thickness_mm,
        color=material.color,
        decor_code=material.decor_code,
        panel_length_mm=material.panel_length_mm,
        panel_width_mm=material.panel_width_mm,
        grain_direction=material.grain_direction,
        image_file_id=material.image_file_id,
        status=material.status,
        created_at=material.created_at,
        updated_at=material.updated_at,
    )


__all__ = [
    "BranchCatalogOption",
    "BranchMaterialRecord",
    "MaterialRecord",
    "add_branch_material",
    "create_manufacturer",
    "create_material",
    "get_manufacturer",
    "get_material",
    "list_branch_catalog_options",
    "list_branch_materials",
    "list_manufacturers",
    "list_materials",
    "material_response_from_models",
    "set_branch_material_status",
    "set_manufacturer_status",
    "set_material_status",
    "update_branch_material",
    "update_manufacturer",
    "update_material",
]
