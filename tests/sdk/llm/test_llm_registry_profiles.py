import json

import pytest
from pydantic import SecretStr

from openhands.sdk.llm.llm import LLM
from openhands.sdk.llm.llm_registry import LLMRegistry


def test_list_profiles_returns_sorted_names(tmp_path):
    registry = LLMRegistry(profile_dir=tmp_path)
    (tmp_path / "b.json").write_text("{}", encoding="utf-8")
    (tmp_path / "a.json").write_text("{}", encoding="utf-8")

    assert registry.list_profiles() == ["a", "b"]


def test_save_profile_excludes_secret_fields(tmp_path):
    registry = LLMRegistry(profile_dir=tmp_path)
    llm = LLM(
        model="gpt-4o-mini",
        service_id="service",
        api_key=SecretStr("secret"),
        aws_access_key_id=SecretStr("id"),
        aws_secret_access_key=SecretStr("value"),
    )

    path = registry.save_profile("sample", llm)
    data = json.loads(path.read_text(encoding="utf-8"))

    assert data["profile_id"] == "sample"
    assert data["service_id"] == "service"
    assert "api_key" not in data
    assert "aws_access_key_id" not in data
    assert "aws_secret_access_key" not in data


def test_save_profile_can_include_secret_fields(tmp_path):
    registry = LLMRegistry(profile_dir=tmp_path)
    llm = LLM(
        model="gpt-4o-mini",
        service_id="service",
        api_key=SecretStr("secret"),
        aws_access_key_id=SecretStr("id"),
        aws_secret_access_key=SecretStr("value"),
    )

    path = registry.save_profile("sample", llm, include_secrets=True)
    data = json.loads(path.read_text(encoding="utf-8"))

    assert data["api_key"] == "secret"
    assert data["aws_access_key_id"] == "id"
    assert data["aws_secret_access_key"] == "value"


def test_load_profile_assigns_profile_id_when_missing(tmp_path):
    registry = LLMRegistry(profile_dir=tmp_path)
    profile_path = tmp_path / "foo.json"
    profile_path.write_text(
        json.dumps({"model": "gpt-4o-mini", "service_id": "svc"}),
        encoding="utf-8",
    )

    llm = registry.load_profile("foo")

    assert llm.profile_id == "foo"
    assert llm.service_id == "svc"


def test_register_profiles_skips_invalid_and_duplicate_profiles(tmp_path):
    registry = LLMRegistry(profile_dir=tmp_path)

    llm = LLM(model="gpt-4o-mini", service_id="shared")
    registry.save_profile("alpha", llm)

    duplicate_data = llm.model_dump(exclude_none=True)
    duplicate_data["profile_id"] = "beta"
    (tmp_path / "beta.json").write_text(
        json.dumps(duplicate_data),
        encoding="utf-8",
    )

    (tmp_path / "gamma.json").write_text("{", encoding="utf-8")

    registry.register_profiles()

    assert registry.list_services() == ["shared"]


def test_validate_profile_reports_errors(tmp_path):
    registry = LLMRegistry(profile_dir=tmp_path)

    ok, errors = registry.validate_profile(
        {"model": "gpt-4o-mini", "service_id": "svc"}
    )
    assert ok
    assert errors == []

    ok, errors = registry.validate_profile({"service_id": "svc"})
    assert not ok
    assert any("model" in message for message in errors)


def test_switch_profile_replaces_active_llm(tmp_path):
    registry = LLMRegistry(profile_dir=tmp_path)
    base_llm = LLM(model="gpt-4o-mini", service_id="service")
    registry.add(base_llm)
    registry.save_profile("alternate", LLM(model="gpt-4o", service_id="alternate"))

    events: list = []
    registry.subscribe(events.append)

    switched = registry.switch_profile("service", "alternate")

    assert switched.profile_id == "alternate"
    assert switched.service_id == "service"
    assert registry.get("service") is switched
    assert switched.model == "gpt-4o"
    assert len(events) == 1
    assert events[0].llm is switched

    # switching to the same profile should be a no-op
    again = registry.switch_profile("service", "alternate")
    assert again is switched
    assert len(events) == 1


def test_switch_profile_unknown_service(tmp_path):
    registry = LLMRegistry(profile_dir=tmp_path)
    with pytest.raises(KeyError):
        registry.switch_profile("missing", "profile")


def test_switch_profile_missing_profile(tmp_path):
    registry = LLMRegistry(profile_dir=tmp_path)
    registry.add(LLM(model="gpt-4o-mini", service_id="service"))

    with pytest.raises(FileNotFoundError):
        registry.switch_profile("service", "does-not-exist")
