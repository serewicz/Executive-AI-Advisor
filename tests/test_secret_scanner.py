from scripts.check_no_secrets import main


def test_secret_scanner_passes_on_tracked_placeholders():
    assert main() == 0
