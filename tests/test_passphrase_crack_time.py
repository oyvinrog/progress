"""Tests for save-passphrase crack-time helper logic."""

from task_model import (
    _build_passphrase_crack_time_report,
    _detect_diceware,
    _estimate_bruteforce_guesses,
    _estimate_human_effective_bits,
    _format_duration_human,
    _infer_charset_size,
    _validate_passphrase_confirmation,
)


def test_infer_charset_size_for_mixed_ascii():
    assert _infer_charset_size("abc") == 26
    assert _infer_charset_size("Abc123") == 62
    assert _infer_charset_size("Abc123!") == 95


def test_estimate_bruteforce_guesses_uses_charset_power_length():
    assert _estimate_bruteforce_guesses("") == 0
    assert _estimate_bruteforce_guesses("ab") == 26 ** 2
    assert _estimate_bruteforce_guesses("a1") == 36 ** 2


def test_human_effective_bits_penalizes_common_patterns():
    common = _estimate_human_effective_bits("password2024")
    stronger = _estimate_human_effective_bits("v9T!q3Lm#8Pz")
    assert stronger > common


def test_format_duration_human_boundaries():
    assert _format_duration_human(0.1) == "less than a second"
    formatted = _format_duration_human(90)
    assert "hours" in formatted
    assert "days" in formatted
    assert "years" in formatted


def test_build_passphrase_crack_time_report_and_validation():
    assert "Enter a passphrase" in _build_passphrase_crack_time_report("")

    report = _build_passphrase_crack_time_report("Tr0ub4dor&3", include_yubikey_note=True)
    assert "Top-end GPU cluster" in report
    assert "Argon2id t=3, m=65536, p=1" in report
    assert "Brute-force (charset^length)" in report
    assert "Human-pattern adjusted" in report
    assert "Expected " in report
    assert "Worst-case " in report
    assert "hours" in report
    assert "days" in report
    assert "years" in report
    assert "YubiKey-derived" in report

    assert _validate_passphrase_confirmation("", "") == (False, "Passphrase cannot be empty.")
    assert _validate_passphrase_confirmation("abc", "") == (False, "Confirm your passphrase.")
    assert _validate_passphrase_confirmation("abc", "xyz") == (False, "Passphrases do not match.")
    assert _validate_passphrase_confirmation("abc", "abc") == (True, "Passphrases match.")


def test_detect_diceware_with_hyphens():
    is_dw, num, pool = _detect_diceware("anthem-cruiser-flyer-tusk-koala-drool")
    assert is_dw is True
    assert num == 6
    assert pool == 7776


def test_detect_diceware_with_spaces():
    is_dw, num, pool = _detect_diceware("anthem cruiser flyer tusk koala drool")
    assert is_dw is True
    assert num == 6


def test_detect_diceware_rejects_short_phrases():
    is_dw, _, _ = _detect_diceware("hello-world")
    assert is_dw is False


def test_detect_diceware_rejects_non_alpha_tokens():
    is_dw, _, _ = _detect_diceware("abc-123-def-456-ghi")
    assert is_dw is False


def test_detect_diceware_rejects_regular_passphrase():
    is_dw, _, _ = _detect_diceware("Tr0ub4dor&3")
    assert is_dw is False


def test_report_uses_wordlist_attack_for_diceware():
    report = _build_passphrase_crack_time_report("anthem-cruiser-flyer-tusk-koala-drool")
    assert "Wordlist attack" in report
    assert "7,776-word list" in report
    assert "77.5 bits" in report
    assert "Brute-force (charset^length)" not in report


def test_report_uses_bruteforce_for_regular_passphrase():
    report = _build_passphrase_crack_time_report("Tr0ub4dor&3")
    assert "Brute-force (charset^length)" in report
    assert "Wordlist attack" not in report
