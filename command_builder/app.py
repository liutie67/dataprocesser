from __future__ import annotations

import sqlite3
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query, Response, status
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .commands import build_command, parse_command
from .models import (
    BackupData,
    CommandDraft,
    GenerateResult,
    HistoryEntry,
    HistoryNoteUpdate,
    ImportRequest,
    ImportResult,
    ParseCommandRequest,
    ParseCommandResult,
    PreviewResult,
    Profile,
    ProfilePayload,
    RecordCommandRequest,
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

    @application.post("/api/commands/parse", response_model=ParseCommandResult)
    def parse_existing_command(request: ParseCommandRequest) -> ParseCommandResult:
        try:
            return parse_command(request)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @application.post("/api/commands/preview", response_model=PreviewResult)
    def preview_command(draft: CommandDraft) -> PreviewResult:
        try:
            return PreviewResult(command=build_command(draft))
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @application.post("/api/commands/record", response_model=GenerateResult)
    def record_command(request: RecordCommandRequest) -> GenerateResult:
        try:
            command = build_command(request.draft)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        profile_id = request.profile_id
        if profile_id is not None and storage.get_profile(profile_id) is None:
            profile_id = None
        snapshot = request.draft.model_dump(mode="json")
        snapshot["name"] = request.profile_name
        if profile_id is not None:
            snapshot["id"] = profile_id
        history = storage.add_history_snapshot(
            profile_id=profile_id,
            profile_name=request.profile_name,
            shell=request.draft.shell.value,
            command=command,
            snapshot=snapshot,
        )
        return GenerateResult(command=command, history=history)

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

    @application.patch("/api/history/{history_id}", response_model=HistoryEntry)
    def update_history_note(
        history_id: str, payload: HistoryNoteUpdate
    ) -> HistoryEntry:
        history = storage.update_history_note(history_id, payload.note)
        if history is None:
            raise HTTPException(status_code=404, detail="找不到该历史记录")
        return history

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
            lines.append(
                f"[{item.created_at.isoformat()}] {item.profile_name} ({item.shell.value})"
            )
            if item.note:
                lines.append(f"# 备注: {item.note}")
            lines.extend([item.command, ""])
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
