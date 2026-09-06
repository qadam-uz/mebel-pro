"""Public catalog API used by routes and other modules."""

from app.modules.catalog.contracts import BranchMaterial, Decor, DecorFormat, Manufacturer
from app.modules.catalog.schemas import (
    BranchMaterialResponse,
    DecorFormatResponse,
    DecorResponse,
)
from app.modules.catalog.service import (
    BranchCatalogFacets,
    BranchCatalogFacetScope,
    BranchCatalogOption,
    BranchCatalogOptionsPage,
    BranchMaterialAttachResult,
    BranchMaterialRecord,
    DecorFormatRecord,
    DecorFormatShape,
    DecorRecord,
    apply_decor_search,
    attach_branch_materials,
    branch_material_join,
    branch_material_label,
    branch_material_snapshot,
    create_decor,
    create_decor_format,
    create_manufacturer,
    decor_format_label,
    decor_format_snapshot,
    decor_label,
    decor_dimension_arms,
    decor_snapshot,
    format_dimension_arms,
    get_decor,
    get_manufacturer,
    list_branch_catalog_facets,
    list_branch_catalog_formats,
    list_branch_catalog_options,
    list_branch_materials,
    list_decor_formats,
    list_decors,
    list_manufacturers,
    normalize_mm,
    set_branch_material_min_stock,
    set_branch_material_status,
    set_decor_format_status,
    set_decor_status,
    set_manufacturer_status,
    update_branch_material,
    update_decor,
    update_manufacturer,
    validate_decor_format_shape,
)


def decor_response_from_models(
    decor: Decor,
    manufacturer: Manufacturer,
    branch_usage_count: int = 0,
    format_count: int = 0,
) -> DecorResponse:
    """Build the public decor response shape from catalog-owned records."""

    return DecorResponse(
        id=decor.id,
        manufacturer_id=decor.manufacturer_id,
        manufacturer_name=manufacturer.name,
        code=decor.code,
        name=decor.name,
        has_grain=decor.has_grain,
        image_file_id=decor.image_file_id,
        status=decor.status,
        label=decor_label(decor, manufacturer),
        branch_usage_count=branch_usage_count,
        format_count=format_count,
        created_at=decor.created_at,
        updated_at=decor.updated_at,
    )


def decor_format_response_from_models(
    decor_format: DecorFormat,
    decor: Decor,
    manufacturer: Manufacturer,
) -> DecorFormatResponse:
    """Build the public decor-format response from catalog-owned records."""

    return DecorFormatResponse(
        id=decor_format.id,
        decor_id=decor_format.decor_id,
        type=decor_format.type,
        thickness_mm=normalize_mm(decor_format.thickness_mm),
        length_mm=decor_format.length_mm,
        width_mm=decor_format.width_mm,
        tape_width_mm=decor_format.tape_width_mm,
        finished_sides=decor_format.finished_sides,
        status=decor_format.status,
        label=decor_format_label(decor_format, decor, manufacturer),
        created_at=decor_format.created_at,
        updated_at=decor_format.updated_at,
    )


def branch_material_response_from_models(
    branch_material: BranchMaterial,
    decor_format: DecorFormat,
    decor: Decor,
    manufacturer: Manufacturer,
) -> BranchMaterialResponse:
    """Build the public branch-material response from catalog-owned records.

    The one builder for this shape: inventory renders stock rows through it too,
    rather than reaching into catalog's private route helpers.
    """

    return BranchMaterialResponse(
        id=branch_material.id,
        branch_id=branch_material.branch_id,
        decor_format_id=branch_material.decor_format_id,
        decor_format=decor_format_response_from_models(decor_format, decor, manufacturer),
        decor=decor_response_from_models(decor, manufacturer),
        price_tiyin=branch_material.price_tiyin,
        price_unset=branch_material.price_tiyin == 0,
        min_stock=branch_material.min_stock,
        status=branch_material.status,
        label=branch_material_label(decor_format, decor, manufacturer, branch_material.id),
        created_at=branch_material.created_at,
        updated_at=branch_material.updated_at,
    )


__all__ = [
    "BranchCatalogFacetScope",
    "BranchCatalogFacets",
    "BranchCatalogOption",
    "BranchCatalogOptionsPage",
    "BranchMaterialAttachResult",
    "BranchMaterialRecord",
    "DecorFormatRecord",
    "DecorFormatShape",
    "DecorRecord",
    "apply_decor_search",
    "attach_branch_materials",
    "branch_material_join",
    "branch_material_label",
    "branch_material_response_from_models",
    "branch_material_snapshot",
    "create_decor",
    "create_decor_format",
    "create_manufacturer",
    "decor_format_label",
    "decor_format_response_from_models",
    "decor_format_snapshot",
    "decor_label",
    "decor_response_from_models",
    "decor_dimension_arms",
    "decor_snapshot",
    "format_dimension_arms",
    "get_decor",
    "get_manufacturer",
    "list_branch_catalog_facets",
    "list_branch_catalog_formats",
    "list_branch_catalog_options",
    "list_branch_materials",
    "list_decor_formats",
    "list_decors",
    "list_manufacturers",
    "normalize_mm",
    "set_branch_material_min_stock",
    "set_branch_material_status",
    "set_decor_format_status",
    "set_decor_status",
    "set_manufacturer_status",
    "update_branch_material",
    "update_decor",
    "update_manufacturer",
    "validate_decor_format_shape",
]
