"""Picker dedup must fold live bare wire-ids into their curated public slug.

Some providers live-discover a model under a bare wire id (``k3``) while the
curated catalog carries the public slug (``kimi-k3``). The curated-first
picker merge must not render both as separate rows for the same model.
"""

from hermes_cli.model_search import model_alias_canonical


class TestModelAliasCanonical:
    def test_bare_k3_folds_to_public_slug(self):
        assert model_alias_canonical("k3") == "kimi-k3"
        assert model_alias_canonical("K3") == "kimi-k3"

