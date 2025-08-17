from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from typing import Optional, Dict, Any
import os
from datetime import datetime
from fastapi.responses import FileResponse

router = APIRouter(prefix="/smpl", tags=["SMPL"])

# Base URL to serve static GLB assets (e.g., your Twin3D host or CDN)
SMPL_ASSETS_BASE_URL = os.getenv("SMPL_ASSETS_BASE_URL", "")  # e.g., https://your-twin-host/models
# Local storage path for uploaded SMPL parameter files (npz/pkl)
SMPL_STORAGE_DIR = os.getenv("SMPL_STORAGE_DIR", os.path.join(os.path.dirname(__file__), "..", "smpl_models"))
SMPL_STORAGE_DIR = os.path.abspath(SMPL_STORAGE_DIR)

# Ensure storage directory exists
os.makedirs(SMPL_STORAGE_DIR, exist_ok=True)


@router.get("/health")
async def smpl_health() -> Dict[str, Any]:
    return {
        "status": "ok",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "assets_base_url": SMPL_ASSETS_BASE_URL or None,
        "storage_dir": SMPL_STORAGE_DIR,
    }


def _select_model(gender: Optional[str], model: Optional[str]) -> str:
    if model in {"male", "female", "neutral"}:
        return model
    if gender in {"male", "female"}:
        return gender
    return "neutral"


def _asset_file_for_model(model: str) -> str:
    # Preferred GLB filenames; client should fallback if missing
    return f"{model}.glb"


@router.get("/generate")
async def smpl_generate(
    patient_id: Optional[str] = None,
    height: Optional[float] = 170.0,
    weight: Optional[float] = 70.0,
    gender: Optional[str] = "neutral",
    model: Optional[str] = None,
    beta1: Optional[float] = None,
) -> Dict[str, Any]:
    try:
        selected_model = _select_model(gender, model)
        asset_file = _asset_file_for_model(selected_model)
        asset_url = (
            f"{SMPL_ASSETS_BASE_URL.rstrip('/')}/{asset_file}"
            if SMPL_ASSETS_BASE_URL
            else None
        )

        # Compute simple derived metrics
        bmi = None
        try:
            if height and weight and height > 0:
                bmi = round(weight / ((height / 100.0) ** 2), 1)
        except Exception:
            bmi = None

        # Return parameters and the asset reference; client decides how to load/apply
        return {
            "status": "ok",
            "patient_id": patient_id,
            "model": selected_model,
            "asset_file": asset_file,
            "asset_url": asset_url,
            "parameters": {
                "height_cm": height,
                "weight_kg": weight,
                "gender": gender,
                "beta1": beta1,
                "bmi": bmi,
            },
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"SMPL generation failed: {e}")


@router.post("/upload_model")
async def upload_smpl_model(
    file: UploadFile = File(...),
    model: str = Form(...),  # male | female | neutral
    fmt: Optional[str] = Form(None),  # optional, inferred from filename if missing
) -> Dict[str, Any]:
    model = model.lower()
    if model not in {"male", "female", "neutral"}:
        raise HTTPException(status_code=400, detail="Invalid model. Use male, female, or neutral.")

    filename = file.filename or ""
    ext = (os.path.splitext(filename)[1] or "").lower()
    if not fmt:
        fmt = ext.lstrip(".") if ext else None

    if fmt not in {"npz", "pkl"}:
        raise HTTPException(status_code=400, detail="Unsupported format. Use npz or pkl.")

    dest_path = os.path.join(SMPL_STORAGE_DIR, f"{model}.{fmt}")

    try:
        contents = await file.read()
        with open(dest_path, "wb") as f:
            f.write(contents)
        return {
            "status": "stored",
            "model": model,
            "format": fmt,
            "bytes": len(contents),
            "path": dest_path,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to store file: {e}")


@router.get("/models")
async def list_smpl_models() -> Dict[str, Any]:
    try:
        files = []
        if os.path.isdir(SMPL_STORAGE_DIR):
            for name in sorted(os.listdir(SMPL_STORAGE_DIR)):
                path = os.path.join(SMPL_STORAGE_DIR, name)
                if os.path.isfile(path) and (name.endswith(".npz") or name.endswith(".pkl")):
                    files.append({
                        "file": name,
                        "size": os.path.getsize(path),
                        "path": path,
                    })
        return {"status": "ok", "files": files}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list models: {e}")


@router.get("/download")
async def download_smpl_model(model: str, fmt: Optional[str] = None):
    model = model.lower()
    if model not in {"male", "female", "neutral"}:
        raise HTTPException(status_code=400, detail="Invalid model. Use male, female, or neutral.")
    candidates = []
    if fmt in {"npz", "pkl"}:
        candidates.append(os.path.join(SMPL_STORAGE_DIR, f"{model}.{fmt}"))
    else:
        candidates.extend([
            os.path.join(SMPL_STORAGE_DIR, f"{model}.npz"),
            os.path.join(SMPL_STORAGE_DIR, f"{model}.pkl"),
        ])
    for path in candidates:
        if os.path.isfile(path):
            return FileResponse(path, filename=os.path.basename(path), media_type="application/octet-stream")
    raise HTTPException(status_code=404, detail="Requested model not found") 