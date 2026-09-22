from pathlib import Path

from fastapi.testclient import TestClient

from command_builder.app import create_app


def test_profile_generate_history_and_exports(tmp_path: Path):
    with TestClient(create_app(tmp_path / "api.sqlite3")) as client:
        payload = {
            "name": "testbench",
            "script_path": r".\testbench.py",
            "prefix": "python",
            "shell": "powershell",
            "arguments": [
                {
                    "id": "budget",
                    "position": 0,
                    "mode": "named",
                    "token": "--budget",
                    "value_type": "int",
                    "value": 120,
                    "choices": [],
                    "enabled": True,
                }
            ],
        }
        created = client.post("/api/profiles", json=payload)
        assert created.status_code == 201
        profile_id = created.json()["id"]

        generated = client.post(f"/api/profiles/{profile_id}/generate")
        assert generated.status_code == 200
        assert generated.json()["command"] == r"python .\testbench.py --budget 120"

        history = client.get("/api/history")
        assert len(history.json()) == 1
        assert history.json()[0]["profile_name"] == "testbench"
        assert history.json()[0]["note"] == ""

        history_id = history.json()[0]["id"]
        noted = client.patch(
            f"/api/history/{history_id}", json={"note": "关键性能参数"}
        )
        assert noted.status_code == 200
        assert noted.json()["note"] == "关键性能参数"
        assert client.get("/api/history", params={"q": "关键性能"}).json()[0][
            "id"
        ] == history_id

        json_export = client.get("/api/export/json")
        assert json_export.status_code == 200
        assert json_export.json()["schema_version"] == 2
        assert json_export.json()["history"][0]["note"] == "关键性能参数"
        assert "attachment" in json_export.headers["content-disposition"]

        txt_export = client.get("/api/export/txt")
        assert txt_export.status_code == 200
        assert "# 备注: 关键性能参数" in txt_export.text
        assert r"python .\testbench.py --budget 120" in txt_export.text


def test_update_history_note_validation_and_missing_record(tmp_path: Path):
    with TestClient(create_app(tmp_path / "history-note.sqlite3")) as client:
        assert client.patch("/api/history/missing", json={"note": "备注"}).status_code == 404
        assert client.patch(
            "/api/history/missing", json={"note": "x" * 501}
        ).status_code == 422


def test_import_merge_and_replace(tmp_path: Path):
    with TestClient(create_app(tmp_path / "source.sqlite3")) as source:
        payload = {
            "name": "配置",
            "script_path": "tool.py",
            "prefix": "uv_run_python",
            "shell": "bash",
            "arguments": [],
        }
        profile = source.post("/api/profiles", json=payload).json()
        source.post(f"/api/profiles/{profile['id']}/generate")
        backup = source.get("/api/export/json").json()

    with TestClient(create_app(tmp_path / "target.sqlite3")) as target:
        merged = target.post("/api/import", json={"mode": "merge", "backup": backup})
        assert merged.status_code == 200
        assert merged.json() == {"profiles_imported": 1, "history_imported": 1}

        replaced = target.post("/api/import", json={"mode": "replace", "backup": backup})
        assert replaced.status_code == 200
        assert len(target.get("/api/profiles").json()) == 1
        assert len(target.get("/api/history").json()) == 1


def test_rejects_duplicate_name_and_invalid_parameter(tmp_path: Path):
    with TestClient(create_app(tmp_path / "errors.sqlite3")) as client:
        payload = {
            "name": "same",
            "script_path": "tool.py",
            "prefix": "python",
            "shell": "powershell",
            "arguments": [],
        }
        assert client.post("/api/profiles", json=payload).status_code == 201
        assert client.post("/api/profiles", json=payload).status_code == 409

        payload["name"] = "invalid"
        payload["arguments"] = [
            {
                "id": "bad",
                "position": 0,
                "mode": "named",
                "token": "budget",
                "value_type": "int",
                "value": 1,
                "enabled": True,
            }
        ]
        assert client.post("/api/profiles", json=payload).status_code == 422


def test_parse_and_preview_do_not_write_data(tmp_path: Path):
    with TestClient(create_app(tmp_path / "parse.sqlite3")) as client:
        parsed = client.post(
            "/api/commands/parse",
            json={
                "command": "py -m package.worker --limit 12 --verbose",
                "dialect": "auto",
                "fallback_shell": "powershell",
            },
        )
        assert parsed.status_code == 200
        draft = parsed.json()["draft"]
        assert draft["invocation_mode"] == "module"
        assert draft["prefix"] == "py"

        preview = client.post("/api/commands/preview", json=draft)
        assert preview.status_code == 200
        assert preview.json()["command"] == "py -m package.worker --limit 12 --verbose"
        assert client.get("/api/profiles").json() == []
        assert client.get("/api/history").json() == []


def test_parse_error_leaves_api_data_untouched(tmp_path: Path):
    with TestClient(create_app(tmp_path / "parse-error.sqlite3")) as client:
        response = client.post(
            "/api/commands/parse",
            json={"command": "python -c 'print(1)'", "dialect": "bash"},
        )
        assert response.status_code == 422
        assert "-c" in response.json()["detail"]
        assert client.get("/api/profiles").json() == []


def test_record_draft_history_without_saving_profile(tmp_path: Path):
    with TestClient(create_app(tmp_path / "record.sqlite3")) as client:
        draft = {
            "script_path": "tool.py",
            "invocation_mode": "script",
            "prefix": "python",
            "shell": "powershell",
            "arguments": [],
        }
        recorded = client.post(
            "/api/commands/record",
            json={"profile_id": None, "profile_name": "未保存配置", "draft": draft},
        )
        assert recorded.status_code == 200
        assert recorded.json()["command"] == "python tool.py"
        assert recorded.json()["history"]["profile_id"] is None
        assert recorded.json()["history"]["snapshot"]["name"] == "未保存配置"
        assert client.get("/api/profiles").json() == []
        assert len(client.get("/api/history").json()) == 1


def test_record_draft_keeps_valid_profile_link(tmp_path: Path):
    with TestClient(create_app(tmp_path / "record-linked.sqlite3")) as client:
        payload = {
            "name": "已保存",
            "script_path": "tool.py",
            "prefix": "python",
            "shell": "powershell",
            "arguments": [],
        }
        profile = client.post("/api/profiles", json=payload).json()
        draft = {key: value for key, value in profile.items() if key in {
            "script_path", "invocation_mode", "prefix", "shell", "arguments"
        }}
        recorded = client.post(
            "/api/commands/record",
            json={"profile_id": profile["id"], "profile_name": "已保存", "draft": draft},
        )
        assert recorded.status_code == 200
        assert recorded.json()["history"]["profile_id"] == profile["id"]
