import pytest

from clipper import delivery


@pytest.mark.parametrize('issue', ['loudness','loudness-unmeasured','resolution'])
def test_warnings_cannot_be_called_passed(issue):
    assert delivery.summary({'shorts':{'ok':True,'issues':[{'level':'warn','code':issue}]}})=='needs_attention'


def test_only_measured_clean_reports_pass_and_absence_is_unmeasured():
    assert delivery.summary({})=='unmeasured'
    assert delivery.summary({'shorts':{'ok':True,'issues':[]}})=='passed'
    assert delivery.summary({'shorts':{'ok':False,'issues':[]}})=='needs_attention'
