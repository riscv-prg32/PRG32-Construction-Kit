"""Messages the server writes have stable keys and are translated (messages.py, ADR-0027).

Every ``say(area, template, ...)`` in the kit's code has its key in the catalogs with exactly that
English (and, through tests/test_i18n.py, a translation in every language); the values it fills in
are the ones the template names; answers carry the key and values next to the English.
"""
from __future__ import annotations

import ast
import html
import json
from pathlib import Path

import pytest

from prg32_construction_kit import i18n, messages

ROOT = Path(__file__).resolve().parent.parent
EN = json.loads((ROOT / "static" / "i18n" / "en.json").read_text())


def say_calls():
    """(file, line, area, template, value names) for every say(...) call in the kit."""
    for path in sorted((ROOT / "prg32_construction_kit").glob("*.py")):
        for node in ast.walk(ast.parse(path.read_text())):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "say":
                area, template = node.args[0], node.args[1]
                assert isinstance(area, ast.Constant) and isinstance(template, ast.Constant), (path.name, node.lineno)
                yield path.name, node.lineno, area.value, template.value, {kw.arg for kw in node.keywords}


CALLS = list(say_calls())


def test_there_are_server_messages_to_check():
    assert len(CALLS) > 200
    assert {area for _file, _line, area, _template, _names in CALLS} >= {"py", "source", "audio", "api", "run", "storage"}


@pytest.mark.parametrize("call", CALLS, ids=lambda call: f"{call[0]}:{call[1]}")
def test_every_message_is_in_the_catalog_with_its_english(call):
    file, line, area, template, names = call
    key = messages.key_for(area, template)
    assert EN.get(key) == template, f"{file}:{line}: add {key!r}: {template!r} to every catalog"
    assert set(messages.PLACEHOLDER.findall(template)) == names, f"{file}:{line}: values do not match the template"


def test_keys_are_stable_and_never_shared():
    assert messages.key_for("py", "{name} is not defined") == messages.key_for("py", "{name} is not defined")
    assert messages.key_for("py", "a b c d e f g") != messages.key_for("py", "a b c d e f h")
    keys = [messages.key_for(area, template) for _f, _l, area, template, _n in CALLS]
    templates = {messages.key_for(area, template): template for _f, _l, area, template, _n in CALLS}
    assert len(set(keys)) == len(templates)


def test_a_message_is_english_text_with_its_key_and_values():
    message = messages.text("py", "{name} is not defined", name="score")
    assert message == "score is not defined" and isinstance(message, str)
    assert messages.fields(message) == {"message_key": message.key, "params": {"name": "score"}}
    assert messages.fields(ValueError(message)) == messages.fields(message)
    assert messages.fields("plain text") == {}


UNDEFINED = messages.key_for("py", "{name} is not defined. Declare it first, for example  {name}: int = 0")
SOURCE = "import prg32\nx: int = 0\n\ndef init() -> None:\n    global x\n    x = y + 1\n\ndef update() -> None:\n    pass\n\ndef draw() -> None:\n    pass\n"


@pytest.mark.parametrize("locale", i18n.LOCALES)
def test_answers_carry_the_key_in_every_language_and_the_english_stays(client, anon, locale):
    client.set_cookie(i18n.COOKIE, locale)
    project = client.post("/api/projects", json={"title": "Keys", "game_json": {
        "source_mode": "python", "source_python": SOURCE}}).get_json()
    body = client.post(f"/api/projects/{project['id']}/convert", json={}).get_json()
    key = UNDEFINED
    assert body["error"] == "Line 6: y is not defined. Declare it first, for example  y: int = 0"
    assert body["message_key"] == key and body["params"] == {"name": "y"}
    assert body["problems"][0]["message_key"] == key
    assert i18n.translate(locale, key, **body["params"]).startswith("y ")
    missing = client.get("/api/artifacts/nope").get_json()
    assert missing["message_key"] == messages.key_for("api", "Not found")
    guest = anon.post("/api/guest/convert", json={"project": {"title": "Keys", "game_json": {
        "source_mode": "python", "source_python": SOURCE}}}).get_json()
    assert guest["message_key"] == key


def test_the_chinese_text_of_a_python_problem():
    assert i18n.translate("zh-Hans", UNDEFINED, name="y") == \
        "y 没有定义。请先声明它，例如  y: int = 0"


@pytest.mark.parametrize("locale", i18n.LOCALES)
def test_server_drawn_pages_and_account_answers_are_in_the_reader_s_language(anon, locale):
    anon.set_cookie(i18n.COOKIE, locale)
    page = anon.post("/auth/login", data={"username": "nobody", "password": "wrong"}).get_data(as_text=True)
    assert i18n.translate(locale, messages.key_for("auth", "Invalid username or password.")) in html.unescape(page)
    answer = anon.post("/auth/login", data={"username": "nobody", "password": "wrong"},
                       headers={"Accept": "application/json"}).get_json()
    assert answer["error"] == "invalid username or password"
    assert answer["message_key"] == messages.key_for("auth", "invalid username or password")
