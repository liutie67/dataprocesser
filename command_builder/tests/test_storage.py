from pathlib import Path

import pytest

from command_builder.commands import build_command
from command_builder.models import ImportMode, ProfilePayload
from command_builder.storage import Storage


@pytest.fixture
def storage(tmp_path: Path) -> Storage:
    return Storage(tmp_path / "command-builder.sqlite3")


def payload(name: str = "测试") -> ProfilePayload:
    return ProfilePayload(
        name=name,
        script_path=r".\testbench.py",
        prefix="python",
        shell="powershell",
        arguments=[
            {
                "id": "budget",
                "position": 0,
                "mode": "named",
                "token": "--budget",
                "value_type": "int",
                "value": 120,
                "enabled": True,
            }
        ],
    )


def test_profile_crud_and_history(storage: Storage):
    created = storage.create_profile(payload())
    assert storage.get_profile(created.id) == created
    assert len(storage.list_profiles()) == 1

    updated_payload = payload("已更新")
    updated_payload.script_path = r"C:\tools\bench.py"
    updated = storage.update_profile(created.id, updated_payload)
    assert updated is not None
    assert updated.name == "已更新"

    command = build_command(updated)
    history = storage.add_history(updated, command)
    assert history.profile_id == updated.id
    assert storage.list_history(query="budget")[0].id == history.id

    assert storage.delete_profile(updated.id)
    retained = storage.get_history(history.id)
    assert retained is not None
    assert retained.profile_id is None
    assert retained.profile_name == "已更新"


def test_export_and_replace_round_trip(storage: Storage, tmp_path: Path):
    profile = storage.create_profile(payload())
    storage.add_history(profile, build_command(profile))
    backup = storage.export_backup()

    restored = Storage(tmp_path / "restored.sqlite3")
    result = restored.import_backup(backup, ImportMode.REPLACE)
    assert result.profiles_imported == 1
    assert result.history_imported == 1
    assert restored.list_profiles()[0].model_dump() == profile.model_dump()
    assert restored.list_history()[0].command == r"python .\testbench.py --budget 120"


def test_merge_renames_conflicting_profile(storage: Storage):
    profile = storage.create_profile(payload())
    storage.add_history(profile, build_command(profile))
    backup = storage.export_backup()

    result = storage.import_backup(backup, ImportMode.MERGE)
    assert result.profiles_imported == 1
    assert len(storage.list_profiles()) == 2
    assert {item.name for item in storage.list_profiles()} == {"测试", "测试（导入 2）"}
    assert len(storage.list_history()) == 2


def test_failed_replace_rolls_back(storage: Storage):
    storage.create_profile(payload())
    backup = storage.export_backup()
    backup.profiles.append(backup.profiles[0].model_copy())

    with pytest.raises(Exception):
        storage.import_backup(backup, ImportMode.REPLACE)
    assert [item.name for item in storage.list_profiles()] == ["测试"]
