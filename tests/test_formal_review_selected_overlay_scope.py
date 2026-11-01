import ast
import unittest
from pathlib import Path
from types import SimpleNamespace

from formal_review_source_loader import read_formal_review_mixin_source


def _load_issue_matches_editor():
    repo_root = Path(__file__).resolve().parents[1]
    source = read_formal_review_mixin_source(repo_root)
    source_path = repo_root / "tests/formal_review_source_loader.py"
    tree = ast.parse(source)
    body = []
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name in {"_safe_int", "_issue_matches_editor"}:
            body.append(node)
    module = ast.Module(body=body, type_ignores=[])
    namespace: dict[str, object] = {"Issue": object}
    exec(compile(module, str(source_path), "exec"), namespace, namespace)
    return namespace["_issue_matches_editor"]


_issue_matches_editor = _load_issue_matches_editor()


class FormalReviewSelectedOverlayScopeTests(unittest.TestCase):
    def test_claim_issue_matches_only_same_claim_editor(self) -> None:
        issue = SimpleNamespace(section="claims", claim_num=1)

        self.assertTrue(_issue_matches_editor(issue, section="claims", claim_num=1))
        self.assertFalse(_issue_matches_editor(issue, section="claims", claim_num=2))
        self.assertFalse(_issue_matches_editor(issue, section="description", claim_num=None))

    def test_non_claim_issue_matches_same_section(self) -> None:
        issue = SimpleNamespace(section="description", claim_num=None)

        self.assertTrue(_issue_matches_editor(issue, section="description"))
        self.assertTrue(_issue_matches_editor(issue, section="description", claim_num=9))
        self.assertFalse(_issue_matches_editor(issue, section="abstract"))


if __name__ == "__main__":
    unittest.main()
