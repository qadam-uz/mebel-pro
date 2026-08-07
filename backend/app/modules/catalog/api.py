"""Public catalog API used by routes and other modules."""

from app.modules.catalog.contracts import BranchMaterial, Dekor, Manufacturer
from app.modules.catalog.schemas import BranchMaterialResponse, DekorResponse
from app.modules.catalog.service import (
    BranchCatalogFacets,
    BranchCatalogOption,
    BranchCatalogOptionsPage,
    BranchMaterialAttachResult,
    BranchMaterialFormat,
    BranchMaterialRecord,
    DekorRecord,
    attach_branch_materials,
    branch_material_label,
    branch_material_snapshot,
    create_dekor,
    create_manufacturer,
    dekor_label,
    dekor_snapshot,
    get_dekor,
    get_manufacturer,
    list_branch_catalog_facets,
    list_branch_catalog_options,
    list_branch_materials,
    list_dekorlar,
    list_manufacturers,
    normalize_mm,
    set_branch_material_status,
    set_dekor_status,
    set_manufacturer_status,
    update_branch_material,
    update_dekor,
    update_manufacturer,
)


def dekor_response_from_models(
    dekor: Dekor,
    manufacturer: Manufacturer,
    branch_usage_count: int = 0,
) -> DekorResponse:
    """Build the public dekor response shape from catalog-owned records."""

    return DekorResponse(
        id=dekor.id,
        manufacturer_id=dekor.manufacturer_id,
        manufacturer_name=manufacturer.name,
        tur=dekor.tur,
        kod=dekor.kod,
        nomi=dekor.nomi,
        tolali=dekor.tolali,
        image_file_id=dekor.image_file_id,
        holat=dekor.holat,
        label=dekor_label(dekor, manufacturer),
        branch_usage_count=branch_usage_count,
        created_at=dekor.created_at,
        updated_at=dekor.updated_at,
    )


def branch_material_response_from_models(
    branch_material: BranchMaterial,
    dekor: Dekor,
    manufacturer: Manufacturer,
) -> BranchMaterialResponse:
    """Build the public branch-material response from catalog-owned records.

    The one builder for this shape: inventory renders stock rows through it too,
    rather than reaching into catalog's private route helpers.
    """

    return BranchMaterialResponse(
        id=branch_material.id,
        branch_id=branch_material.branch_id,
        dekor_id=branch_material.dekor_id,
        dekor=dekor_response_from_models(dekor, manufacturer),
        qalinlik_mm=normalize_mm(branch_material.qalinlik_mm),
        uzunlik_mm=branch_material.uzunlik_mm,
        eni_mm=branch_material.eni_mm,
        kromka_eni_mm=branch_material.kromka_eni_mm,
        price_tiyin=branch_material.price_tiyin,
        price_unset=branch_material.price_tiyin == 0,
        min_stock=branch_material.min_stock,
        status=branch_material.status,
        label=branch_material_label(branch_material, dekor, manufacturer),
        created_at=branch_material.created_at,
        updated_at=branch_material.updated_at,
    )


__all__ = [
    "BranchCatalogFacets",
    "BranchCatalogOption",
    "BranchCatalogOptionsPage",
    "BranchMaterialAttachResult",
    "BranchMaterialFormat",
    "BranchMaterialRecord",
    "DekorRecord",
    "attach_branch_materials",
    "branch_material_label",
    "branch_material_response_from_models",
    "branch_material_snapshot",
    "create_dekor",
    "create_manufacturer",
    "dekor_label",
    "dekor_response_from_models",
    "dekor_snapshot",
    "get_dekor",
    "get_manufacturer",
    "list_branch_catalog_facets",
    "list_branch_catalog_options",
    "list_branch_materials",
    "list_dekorlar",
    "list_manufacturers",
    "normalize_mm",
    "set_branch_material_status",
    "set_dekor_status",
    "set_manufacturer_status",
    "update_branch_material",
    "update_dekor",
    "update_manufacturer",
]
