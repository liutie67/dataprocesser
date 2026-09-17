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

        json_export = client.get("/api/export/json")
        assert json_export.status_code == 200
        assert json_export.json()["schema_version"] == 1
        assert "attachment" in json_export.headers["content-disposition"]

        txt_export = client.get("/api/export/txt")
        assert txt_export.status_code == 200
        assert r"python .\testbench.py --budget 120" in txt_export.text


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
