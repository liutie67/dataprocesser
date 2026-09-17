from __future__ import annotations

import sqlite3
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query, Response, status
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .commands import build_command
from .models import (
    BackupData,
    GenerateResult,
    HistoryEntry,
    ImportRequest,
    ImportResult,
    Profile,
    ProfilePayload,
)
from .storage import Storage


PACKAGE_DIR = Path(__file__).resolve().parent
STATIC_DIR = PACKAGE_DIR / "static"
DEFAULT_DATABASE = PACKAGE_DIR / "data" / "command_builder.sqlite3"


def create_app(database_path: Path | None = None) -> FastAPI:
    application = FastAPI(
        title="本地 Python 命令生成器",
        version="1.0.0",
        docs_url="/api/docs",
        redoc_url=None,
    )
    storage = Storage(database_path or DEFAULT_DATABASE)
    application.state.storage = storage
    application.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    @application.get("/", include_in_schema=False)
    def index() -> FileResponse:
        return FileResponse(STATIC_DIR / "index.html")

    @application.get("/api/profiles", response_model=list[Profile])
    def list_profiles() -> list[Profile]:
        return storage.list_profiles()

    @application.post(
        "/api/profiles", response_model=Profile, status_code=status.HTTP_201_CREATED
    )
    def create_profile(payload: ProfilePayload) -> Profile:
        try:
            return storage.create_profile(payload)
        except sqlite3.IntegrityError as exc:
            raise HTTPException(status_code=409, detail="配置名称已存在") from exc

    @application.put("/api/profiles/{profile_id}", response_model=Profile)
    def update_profile(profile_id: str, payload: ProfilePayload) -> Profile:
        try:
            profile = storage.update_profile(profile_id, payload)
        except sqlite3.IntegrityError as exc:
            raise HTTPException(status_code=409, detail="配置名称已存在") from exc
        if profile is None:
            raise HTTPException(status_code=404, detail="找不到该配置")
        return profile

    @application.delete(
        "/api/profiles/{profile_id}", status_code=status.HTTP_204_NO_CONTENT
    )
    def delete_profile(profile_id: str) -> Response:
        if not storage.delete_profile(profile_id):
            raise HTTPException(status_code=404, detail="找不到该配置")
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    @application.post(
        "/api/profiles/{profile_id}/generate", response_model=GenerateResult
    )
    def generate(profile_id: str) -> GenerateResult:
        profile = storage.get_profile(profile_id)
        if profile is None:
            raise HTTPException(status_code=404, detail="找不到该配置")
        try:
            command = build_command(profile)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        history = storage.add_history(profile, command)
        return GenerateResult(command=command, history=history)

    @application.get("/api/history", response_model=list[HistoryEntry])
    def list_history(
        q: str = Query(default="", max_length=200),
        limit: int = Query(default=500, ge=1, le=5000),
    ) -> list[HistoryEntry]:
        return storage.list_history(query=q.strip(), limit=limit)

    @application.delete(
        "/api/history/{history_id}", status_code=status.HTTP_204_NO_CONTENT
    )
    def delete_history(history_id: str) -> Response:
        if not storage.delete_history(history_id):
            raise HTTPException(status_code=404, detail="找不到该历史记录")
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    @application.delete("/api/history", status_code=status.HTTP_204_NO_CONTENT)
    def clear_history() -> Response:
        storage.clear_history()
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    @application.get("/api/export/json", response_model=BackupData)
    def export_json() -> Response:
        backup = storage.export_backup()
        return Response(
            content=backup.model_dump_json(indent=2),
            media_type="application/json; charset=utf-8",
            headers={
                "Content-Disposition": "attachment; filename=command-builder-backup.json"
            },
        )

    @application.get("/api/export/txt")
    def export_txt() -> Response:
        backup = storage.export_backup()
        lines = [
            "# Command Builder 历史命令",
            f"# 导出时间: {backup.exported_at.isoformat()}",
            "",
        ]
        for item in reversed(backup.history):
            lines.extend(
                [
                    f"[{item.created_at.isoformat()}] {item.profile_name} ({item.shell.value})",
                    item.command,
                    "",
                ]
            )
        return Response(
            content="\n".join(lines),
            media_type="text/plain; charset=utf-8",
            headers={
                "Content-Disposition": "attachment; filename=command-builder-history.txt"
            },
        )

    @application.post("/api/import", response_model=ImportResult)
    def import_json(request: ImportRequest) -> ImportResult:
        try:
            return storage.import_backup(request.backup, request.mode)
        except sqlite3.IntegrityError as exc:
            raise HTTPException(status_code=409, detail="备份中存在冲突数据") from exc
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    return application


app = create_app()
