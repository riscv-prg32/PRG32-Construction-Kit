"""A Blocks game has one and only one of each event block (docs/blockly.md).

'when game starts', 'every frame update' and 'every frame draw' are the bodies of
<prefix>_init, <prefix>_update and <prefix>_draw: a missing or an extra copy is refused,
with a message that names the block, before any code is generated.
"""
from __future__ import annotations

import pytest

from prg32_construction_kit import messages
from prg32_construction_kit.generator import EVENT_BLOCKS, EventBlockError, blocks_to_c, blocks_to_ir
from prg32_construction_kit.routes import generate_sources
from prg32_construction_kit.sample_data import default_blocks


def workspace(*types):
    return {"blocks": {"languageVersion": 0, "blocks": [{"type": kind, "id": f"b{i}"} for i, kind in enumerate(types)]}}


ALL = tuple(EVENT_BLOCKS)


def test_one_of_each_is_accepted():
    ir = blocks_to_ir(workspace(*ALL), {"title": "Ok"})
    assert ir["entry_prefix"] == "ok"
    blocks_to_ir(default_blocks(), {"title": "Hello"})


@pytest.mark.parametrize("missing", ALL)
def test_a_missing_event_block_is_refused(missing):
    with pytest.raises(EventBlockError) as caught:
        blocks_to_ir(workspace(*[kind for kind in ALL if kind != missing]), {"title": "Missing"})
    assert caught.value.block_type == missing and caught.value.block_ids == []
    assert f"'{EVENT_BLOCKS[missing]}'" in str(caught.value)


@pytest.mark.parametrize("extra", ALL)
def test_an_extra_event_block_is_refused(extra):
    with pytest.raises(EventBlockError) as caught:
        blocks_to_c(workspace(*ALL, extra, extra), {"title": "Extra"})
    assert caught.value.block_type == extra
    assert caught.value.block_ids == ["b3", "b4"]   # the copies after the first
    assert str(caught.value).startswith(f"There are 3 '{EVENT_BLOCKS[extra]}' blocks")


def test_an_empty_workspace_is_refused():
    with pytest.raises(EventBlockError):
        blocks_to_ir({}, {"title": "Empty"})


def test_the_refusal_is_a_translatable_message():
    project = {"title": "Twice", "blocks_json": workspace(*ALL, "prg32_draw")}
    game_ir, c_source, refusal = generate_sources(project)
    assert game_ir is None and c_source is None
    assert messages.fields(refusal) == {"message_key": messages.key_for("blocks", "There are {count} '{block}' blocks: "
                                        "a Blocks game needs exactly one. Move their blocks into one of them and delete the others"),
                                        "params": {"count": 2, "block": "every frame draw"}}
    assert not str(refusal).startswith("Conversion failed")
