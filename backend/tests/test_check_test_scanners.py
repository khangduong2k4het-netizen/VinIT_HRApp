import importlib.util
from pathlib import Path
from unittest.mock import Mock

from app.services.malware_scan import ScanVerdict
from app.services.spam_scan import SpamVerdict

spec = importlib.util.spec_from_file_location('check_test_scanners', Path(__file__).resolve().parents[1] / 'scripts/check_test_scanners.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_scanner_smoke_reports_correct_verdicts(monkeypatch):
    av = Mock(side_effect=[ScanVerdict.INFECTED, ScanVerdict.CLEAN])
    spam = Mock(side_effect=[SpamVerdict.SPAM, SpamVerdict.HAM])
    monkeypatch.setattr(module, 'scan_bytes', av)
    monkeypatch.setattr(module, 'scan_message', spam)
    result = module.run_checks('/tmp/clam.sock', '/tmp/spamd.sock')
    assert result == {'clamav_clean': 'CLEAN', 'clamav_eicar': 'INFECTED', 'spamd_clean': 'HAM', 'spamd_gtube': 'SPAM', 'pass': True}
    assert av.call_count == 2 and spam.call_count == 2


def test_scanner_smoke_fails_closed(monkeypatch):
    monkeypatch.setattr(module, 'scan_bytes', Mock(return_value=ScanVerdict.UNAVAILABLE))
    monkeypatch.setattr(module, 'scan_message', Mock(return_value=SpamVerdict.UNAVAILABLE))
    assert module.run_checks('/tmp/clam.sock', '/tmp/spamd.sock')['pass'] is False
