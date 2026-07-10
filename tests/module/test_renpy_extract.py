from module.Renpy.renpy_extract import ExtractFromFile
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
