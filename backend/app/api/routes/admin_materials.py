"""Platform material master catalog (superadmin app). Platform-operator only."""

import uuid

from fastapi import APIRouter

from app.api.deps import CurrentPlatformUser, Session
from app.models.enums import MaterialKind
from app.schemas.catalog import MaterialCreate, MaterialOut, MaterialUpdate
from app.services import catalog as catalog_service

router = APIRouter()


@router.get("", response_model=list[MaterialOut])
async def list_materials(
    _: CurrentPlatformUser,
    db: Session,
    active_only: bool = False,
    kind: MaterialKind | None = None,
) -> list[MaterialOut]:
    rows = await catalog_service.list_materials(db, active_only=active_only, kind=kind)
    return [MaterialOut.model_validate(m) for m in rows]


@router.post("", response_model=MaterialOut, status_code=201)
async def create_material(
    body: MaterialCreate, actor: CurrentPlatformUser, db: Session
) -> MaterialOut:
    material = await catalog_service.create_material(
        db,
        actor,
        kind=body.kind,
        type_=body.type,
        name=body.name,
        thickness_mm=body.thickness_mm,
        color=body.color,
        decor_code=body.decor_code,
        sheet_length_mm=body.sheet_length_mm,
        sheet_width_mm=body.sheet_width_mm,
        grain_direction=body.grain_direction,
        image_file_id=body.image_file_id,
    )
    return MaterialOut.model_validate(material)


@router.get("/{material_id}", response_model=MaterialOut)
async def get_material(material_id: uuid.UUID, _: CurrentPlatformUser, db: Session) -> MaterialOut:
    material = await catalog_service.get_material(db, material_id)
    return MaterialOut.model_validate(material)


@router.patch("/{material_id}", response_model=MaterialOut)
async def edit_material(
    material_id: uuid.UUID, body: MaterialUpdate, actor: CurrentPlatformUser, db: Session
) -> MaterialOut:
    material = await catalog_service.edit_material(
        db,
        actor,
        material_id,
        type_=body.type,
        type_set=body.type_set,
        name=body.name,
        thickness_mm=body.thickness_mm,
        color=body.color,
        decor_code=body.decor_code,
        decor_code_set=body.decor_code_set,
        sheet_length_mm=body.sheet_length_mm,
        sheet_width_mm=body.sheet_width_mm,
        grain_direction=body.grain_direction,
        image_file_id=body.image_file_id,
        image_file_id_set=body.image_file_id_set,
    )
    return MaterialOut.model_validate(material)


@router.post("/{material_id}/activate", response_model=MaterialOut)
async def activate_material(
    material_id: uuid.UUID, actor: CurrentPlatformUser, db: Session
) -> MaterialOut:
    material = await catalog_service.set_material_status(db, actor, material_id, active=True)
    return MaterialOut.model_validate(material)


@router.post("/{material_id}/deactivate", response_model=MaterialOut)
async def deactivate_material(
    material_id: uuid.UUID, actor: CurrentPlatformUser, db: Session
) -> MaterialOut:
    material = await catalog_service.set_material_status(db, actor, material_id, active=False)
    return MaterialOut.model_validate(material)
