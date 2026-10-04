"""Thin MyRoad learner UI (FastAPI + Jinja). Signed-in users and agents may publish."""

from myroad_core.ui.app import create_learner_app

__all__ = ["create_learner_app"]
