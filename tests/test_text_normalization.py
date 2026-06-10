from app.advisor.text import normalize_text_field


def test_normalize_text_field_preserves_plain_string():
    assert normalize_text_field("Acquisition risk is material. [S1]") == "Acquisition risk is material. [S1]"


def test_normalize_text_field_joins_sentence_list():
    value = ["Security governance is incomplete. [S1]", "Board monitoring should increase. [S2]"]

    assert normalize_text_field(value) == "Security governance is incomplete. [S1] Board monitoring should increase. [S2]"


def test_normalize_text_field_repairs_character_list():
    value = list("Acquisition integration risk is high. [S1]")

    assert normalize_text_field(value) == "Acquisition integration risk is high. [S1]"


def test_normalize_text_field_repairs_character_lines():
    value = "\n".join(list("Acquisition integration risk is high. [S1]"))

    assert normalize_text_field(value) == "Acquisition integration risk is high. [S1]"


def test_normalize_text_field_removes_duplicate_compressed_text():
    sentence = "Manual deployment creates integration risk and operational fragility. [S1]"
    duplicated = f"{sentence} {sentence}"

    assert normalize_text_field(duplicated) == sentence
