from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from app.local_repositories import grant

router = APIRouter(prefix="/v1/local-repositories", tags=["Desktop repository selection"])


class Selection(BaseModel):
    path: str = Field(min_length=1, max_length=4096)


@router.post("/grant")
def selected_folder(selection: Selection):
    # Rust denies this path in the general renderer API bridge. Its native
    # picker calls it internally, using the runtime token held by the host.
    try:
        return {"path": grant(selection.path)}
    except (OSError, ValueError) as exc:
        raise HTTPException(422, "所选目录不允许扫描") from exc
