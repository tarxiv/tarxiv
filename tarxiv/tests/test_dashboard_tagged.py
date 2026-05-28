import importlib

import dash
import pytest


@pytest.fixture
def tagged_module(monkeypatch):
    monkeypatch.setattr(dash, "register_page", lambda *args, **kwargs: None)
    import tarxiv.dashboard.pages.tagged as tagged

    return importlib.reload(tagged)


def test_tag_option_label_team_uses_team_name(tagged_module):
    label = tagged_module.tag_option_label({
        "name": "follow-up",
        "owner_type": "team",
        "owner_name": "Classifiers",
    })
    assert label == "follow-up (team: Classifiers)"


def test_tag_option_label_team_without_name_falls_back(tagged_module):
    label = tagged_module.tag_option_label({"name": "follow-up", "owner_type": "team"})
    assert label == "follow-up (team: team)"


def test_tag_option_label_personal(tagged_module):
    label = tagged_module.tag_option_label({
        "name": "interesting",
        "owner_type": "user",
    })
    assert label == "interesting (personal)"
