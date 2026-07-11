from module.Renpy.renpy_extract import ExtractFromFile
from module.Renpy import renpy_extract as rx
from module.Extract.ReplaceGenerator import (
    _extract_relaxed_english_line_literals,
    _try_load_regex_cache,
)
from module.Extract.UnifiedExtractor import UnifiedExtractor
import types


def extract_from_text(tmp_path, content: str, filter_length: int = 20) -> set[str]:
    path = tmp_path / "script.rpy"
    path.write_text(content, encoding="utf-8")
    return ExtractFromFile(str(path), True, filter_length, False, False, False)


def test_extract_from_file_keeps_short_menu_options_with_suffixes(tmp_path):
    content = '''menu:
    "Option A"(_choice='a'):
        jump label_a
    "Option B":
        pass
    "Option C" if player.money >= 20:
        jump label_c
    "Option D":
        pass
menu location_hall.choice:
    "Option E" if event.peek(choice='e', who=character):
        return event.emit(choice='e', who=character)
    "Option F":
        pass
'''

    result = extract_from_text(tmp_path, content)

    assert {"Option A", "Option B", "Option C", "Option D", "Option E", "Option F"} <= result
    assert "a" not in result
    assert "e" not in result


def test_extract_from_file_ignores_contraction_apostrophes_inside_double_quotes(tmp_path):
    content = '''"You're, ain't"
'''

    result = extract_from_text(tmp_path, content, filter_length=9999)

    assert result == set()


def test_extract_from_file_keeps_double_quoted_dialogue_with_nested_single_quotes(tmp_path):
    content = '''narrator "I've got one minute to top off the reactor and prime the 'luma-drive' core."
'''

    result = extract_from_text(tmp_path, content, filter_length=4)

    assert "I've got one minute to top off the reactor and prime the 'luma-drive' core." in result
    assert "ve got one minute to top off the reactor and prime the " not in result
    assert "luma-drive" not in result


def test_extract_from_file_keeps_double_quoted_dialogue_with_contractions(tmp_path):
    content = '''narrator "Well, it's a clean sweep!"
'''

    result = extract_from_text(tmp_path, content, filter_length=4)

    assert "Well, it's a clean sweep!" in result
    assert "s a clean sweep!" not in result


def test_extract_from_file_keeps_menu_text_with_contraction_and_single_quoted_suffix(tmp_path):
    content = '''menu:
    "I won't decline."(_route='accept'):
        jump accept_route
'''

    result = extract_from_text(tmp_path, content, filter_length=4)

    assert "I won't decline." in result
    assert "accept" not in result
    assert "t decline.\"(_route=" not in result


def test_extract_from_file_ignores_single_quoted_control_conditions(tmp_path):
    content = '''if state == 'start':
    pass
elif state == 'middle':
    pass
while state == 'loop':
    pass
if ready: 'Inline translatable text'
'''

    result = extract_from_text(tmp_path, content, filter_length=5)

    assert {"start", "middle", "loop"}.isdisjoint(result)
    assert "Inline translatable text" in result


def test_extract_from_file_keeps_single_quoted_display_text_outside_double_quotes(tmp_path):
    content = '''show text 'Single quoted display text'
'''

    result = extract_from_text(tmp_path, content, filter_length=4)

    assert "Single quoted display text" in result



def test_replace_text_relaxed_scan_ignores_apostrophes_in_dialogue():
    line = 'speaker "I\'ve got forty seconds to refill the engine and prime her \'aux-drive\' gauge."'

    result = _extract_relaxed_english_line_literals(line)

    assert "I've got forty seconds to refill the engine and prime her 'aux-drive' gauge." in result
    assert 've got forty seconds to refill the engine and prime her ' not in result
    assert 'aux-drive' not in result
    assert _extract_relaxed_english_line_literals("show text 'Standalone display text'") == {"Standalone display text"}


def test_incremental_coverage_ignores_translate_block_comments(tmp_path):
    translation_file = tmp_path / "dialogue.rpy"
    translation_file.write_text(
        'translate chinese scene_demo:\n'
        '    # narrator "I won\'t decline."\n'
        '    narrator "Already translated"\n',
        encoding="utf-8",
    )
    extractor = UnifiedExtractor.__new__(UnifiedExtractor)
    extractor.logger = types.SimpleNamespace(debug=lambda *args, **kwargs: None)

    covered = extractor._get_all_originals(tmp_path)

    assert "I won't decline." not in covered


def test_replace_text_rebuilds_outdated_regex_cache(tmp_path):
    cache_path = tmp_path / "regex_extracted.json"
    cache_path.write_text(
        '{"version": 1, "file_count": 1, "max_mtime_ns": 1, "strings": ["stale fragment"]}',
        encoding="utf-8",
    )

    assert _try_load_regex_cache(cache_path, file_count=1, max_mtime_ns=1) is None


def test_incremental_merge_cleans_staging_folder_and_base_box_placeholders(tmp_path):
    game_dir = tmp_path / "project"
    tl_dir = game_dir / "game" / "tl" / "chinese"
    staging_dir = game_dir / "game" / "tl" / "chinese_new"
    base_box = tl_dir / "base_box"
    base_box.mkdir(parents=True)
    staging_dir.mkdir(parents=True)

    (base_box / "screens_box.rpy").write_text(
        'translate chinese strings:\n\n    old "Back"\n    new "\u8fd4\u56de"\n',
        encoding="utf-8",
    )
    hud = tl_dir / "src" / "gui" / "hud.rpy"
    hud.parent.mkdir(parents=True)
    hud.write_text(
        'translate chinese strings:\n\n    old "Back"\n    new "Back"\n',
        encoding="utf-8",
    )
    staging = staging_dir / "src" / "plot" / "new_text.rpy"
    staging.parent.mkdir(parents=True)
    staging.write_text(
        'translate chinese strings:\n\n    old "New menu text"\n    new "\u65b0\u83dc\u5355\u6587\u672c"\n',
        encoding="utf-8",
    )

    extractor = UnifiedExtractor.__new__(UnifiedExtractor)
    extractor.logger = types.SimpleNamespace(
        debug=lambda *args, **kwargs: None,
        info=lambda *args, **kwargs: None,
        warning=lambda *args, **kwargs: None,
    )
    result = extractor.merge_incremental_folder(game_dir, "chinese", staging_dir, clean_duplicates=True)

    assert result.success
    assert not staging_dir.exists()
    assert 'old "Back"' not in hud.read_text(encoding="utf-8")
    assert 'old "New menu text"' in (tl_dir / "src" / "plot" / "new_text.rpy").read_text(encoding="utf-8")



def test_static_supplement_uses_first_source_file_for_duplicate_menu_text(tmp_path):
    project = tmp_path / "project"
    first_source = project / "game" / "src" / "chapter01.rpy"
    second_source = project / "game" / "src" / "chapter02.rpy"
    first_source.parent.mkdir(parents=True)
    first_source.write_text(
        "menu:\n"
        "    \"Continue route.\"(_choice='continue'):\n"
        "        pass\n",
        encoding="utf-8",
    )
    second_source.write_text(
        "menu:\n"
        "    \"Continue route.\"(_choice='continue'):\n"
        "        pass\n",
        encoding="utf-8",
    )

    candidates = rx.collect_static_source_strings(project)
    assert candidates["Continue route."] == "src/chapter01.rpy"

    extractor = UnifiedExtractor.__new__(UnifiedExtractor)
    extractor.logger = types.SimpleNamespace(info=lambda *args, **kwargs: None)
    tl_dir = project / "_temp" / "game" / "tl" / "chinese"
    assert extractor._append_static_supplement_entries(project, tl_dir, "chinese") >= 1

    first_tl = tl_dir / "src" / "chapter01.rpy"
    second_tl = tl_dir / "src" / "chapter02.rpy"
    assert 'old "Continue route."' in first_tl.read_text(encoding="utf-8")
    assert not second_tl.exists()

    dialogue_tl = tl_dir / "dialogue.rpy"
    dialogue_tl.write_text(
        'translate chinese scene_demo:\n'
        '    # narrator "Continue route."\n'
        '    narrator "Existing dialogue"\n',
        encoding="utf-8",
    )
    assert extractor._remove_string_duplicates_with_blocks(tl_dir) == 0
    assert 'old "Continue route."' in first_tl.read_text(encoding="utf-8")
