import csv
from io import BytesIO, StringIO
from pathlib import PurePosixPath
from urllib.parse import quote
from uuid import uuid4

from fastapi import APIRouter, File, HTTPException, Request, Response, UploadFile
from PIL import Image, UnidentifiedImageError
from pypdf import PdfReader
from pypdf.errors import PdfReadError
from sqlalchemy import insert, select

from ..auth import Db, Denied, Identity, audit
from ..db import utc_now
from ..models import assets, report_assets, version_assets
from ..outputs import Asset, CsvPreview, Page
from .common import Limit, Offset, count, page, take
from .reports import can_edit_working_report, get_report, get_version

router = APIRouter(tags=["文件"])
MAX_BYTES = 5 * 1024 * 1024
TYPES = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".pdf": "application/pdf", ".csv": "text/csv"}

def csv_rows(content, limit=100):
    text = content.decode("utf-8-sig")
    if "\0" in text:
        raise ValueError("Binary CSV")
    reader = csv.reader(StringIO(text, newline=""), strict=True)
    head = next(reader, [])
    if not head or len(head) > 30 or not any(value.strip() for value in head):
        raise ValueError("Invalid CSV header")
    preview = []
    count = 0
    for row in reader:
        if not row:
            continue
        if len(row) != len(head):
            raise ValueError("CSV row length does not match header")
        count += 1
        if len(preview) < limit:
            preview.append(row)
    return {"headers": head, "rows": preview, "total_rows": count}

def inspect(filename, content):
    extension = PurePosixPath(filename).suffix.lower()
    mime = TYPES.get(extension)
    try:
        if not content or not mime:
            raise ValueError()
        if mime.startswith("image/"):
            with Image.open(BytesIO(content)) as image:
                expected = "PNG" if mime == "image/png" else "JPEG"
                if image.format != expected or image.width * image.height > 24_000_000:
                    raise ValueError()
                image.verify()
        elif mime == "application/pdf":
            if not content.startswith(b"%PDF-"):
                raise ValueError()
            reader = PdfReader(BytesIO(content), strict=True)
            if reader.is_encrypted or not reader.pages:
                raise ValueError()
        else:
            csv_rows(content, limit=0)
    except (ValueError, OSError, SyntaxError, UnidentifiedImageError, Image.DecompressionBombError, PdfReadError,
            IndexError, KeyError, RecursionError, csv.Error):
        raise HTTPException(415, "文件内容无效。支持 PNG、JPEG、未加密的 PDF 和 UTF-8 CSV。") from None
    return mime

@router.get("/assets", response_model=Page[Asset])
def list_assets(session: Db, actor: Identity, limit: Limit = 20, offset: Offset = 0):
    actor.scope("asset.upload", "asset")
    owned = assets.c.owner_id == actor.id
    items = select(assets.c.id, assets.c.filename, assets.c.mime, assets.c.size_bytes).where(owned)
    return page(session, items.order_by(assets.c.id.desc()), count(assets, owned), limit, offset)

@router.post("/assets", status_code=201, response_model=Asset)
def upload(request: Request, session: Db, actor: Identity, file: UploadFile = File(...)):
    actor.scope("asset.upload", "asset")
    filename = PurePosixPath((file.filename or "").replace("\\", "/")).name
    if not filename or len(filename) > 200 or any(ord(char) < 32 for char in filename):
        raise HTTPException(422, "文件名无效。")
    content = file.file.read(MAX_BYTES + 1)
    if len(content) > MAX_BYTES:
        raise HTTPException(413, "单文件上限为 5 MiB。")
    mime = inspect(filename, content)
    key = uuid4().hex
    storage = request.app.state.storage
    storage.put(key, content)
    try:
        asset_id = session.execute(insert(assets).values(owner_id=actor.id, storage_key=key,
                                   filename=filename, mime=mime, size_bytes=len(content),
                                   created_at=utc_now())).inserted_primary_key[0]
        audit(session, actor.id, "asset.upload", "asset", asset_id)
        session.commit()
    except Exception:
        storage.delete(key)
        raise
    return {"id": asset_id, "filename": filename, "mime": mime, "size_bytes": len(content)}

def authorize(session, actor, id_, report_id, version):
    if report_id is None:
        if version is not None:
            raise HTTPException(422, "指定版本时必须提供 report_id。")
        file = take(session, assets, id_, "文件")
        if file["owner_id"] != actor.id:
            raise Denied(actor.id, "asset.read", "asset", id_)
        return file
    report = get_report(session, actor, report_id, "report.read")
    if version is None and not can_edit_working_report(report, actor):
        version = report["current_version"]
    if version is None:
        get_report(session, actor, report_id, "report.edit")
        linked = session.scalar(select(report_assets.c.asset_id).where(report_assets.c.report_id == report_id,
                                                                        report_assets.c.asset_id == id_))
    else:
        get_version(session, report_id, version)
        linked = session.scalar(select(version_assets.c.asset_id).where(version_assets.c.report_id == report_id,
                                     version_assets.c.version == version, version_assets.c.asset_id == id_))
    if linked is None:
        raise Denied(actor.id, "asset.read", "asset", id_)
    return take(session, assets, id_, "文件")

def load_file(request, session, actor, id_, report_id, version):
    file = authorize(session, actor, id_, report_id, version)
    try:
        return file, request.app.state.storage.get(file["storage_key"])
    except FileNotFoundError:
        raise HTTPException(404, "存储中没有找到该文件。") from None

@router.get("/assets/{asset_id}/content")
def content(asset_id: int, request: Request, session: Db, actor: Identity, report_id: int | None = None,
            version: int | None = None, download: bool = False):
    file, data = load_file(request, session, actor, asset_id, report_id, version)
    disposition = "attachment" if download or file["mime"] == "text/csv" else "inline"
    return Response(data, media_type=file["mime"], headers={
        "Content-Disposition": f"{disposition}; filename*=UTF-8''{quote(file['filename'], safe='')}",
        "X-Content-Type-Options": "nosniff", "Cache-Control": "private, no-store",
    })

@router.get("/assets/{asset_id}/csv", response_model=CsvPreview)
def preview_csv(asset_id: int, request: Request, session: Db, actor: Identity, report_id: int | None = None,
                version: int | None = None):
    file, data = load_file(request, session, actor, asset_id, report_id, version)
    if file["mime"] != "text/csv":
        raise HTTPException(415, "只有 CSV 文件可以使用表格预览。")
    return csv_rows(data)
