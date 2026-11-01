from __future__ import annotations

import unittest
from pathlib import Path

from core.formal_review.extractor import extract_formal_review_document_from_doc
from core.formal_review.service import run_formal_review


REAL_DOC = Path(__file__).resolve().parents[1] / "test" / "一种软包装封口密封性检测方法及系统和设备（预审）(4).docx"


class FormalReviewExtractorClaimNumberingRealDocTests(unittest.TestCase):
    def test_real_doc_claim_numbers_and_reference_issues(self) -> None:
        if not REAL_DOC.exists():
            self.skipTest(f"real doc fixture missing: {REAL_DOC}")

        try:
            import win32com.client  # type: ignore
        except Exception as exc:
            self.skipTest(f"pywin32 not available: {exc}")

        word = None
        doc = None
        try:
            word = win32com.client.DispatchEx("Word.Application")
            word.Visible = False
            word.DisplayAlerts = 0
            doc = word.Documents.Open(str(REAL_DOC), ReadOnly=True, AddToRecentFiles=False)

            document, _anchors, _segments, _projections = extract_formal_review_document_from_doc(doc)
            claim_nums = [int(getattr(item, "num", 0) or 0) for item in list(getattr(document, "claims", []) or [])]
            self.assertTrue(all(num in claim_nums for num in (1, 2, 3, 4, 5, 6, 7, 8)), claim_nums)

            result = run_formal_review(
                document,
                wordlists={},
                ignored_issue_ids=set(),
                abstract_threshold=300,
            )
            issues = list(result.get("issues", []) or [])
            claim1_ref_issues = [
                issue
                for issue in issues
                if int(getattr(issue, "claim_num", 0) or 0) == 1
                and str(getattr(issue, "rule_id", "") or "") in {"claim.ref.self", "claim.ref.future"}
            ]
            self.assertEqual([], claim1_ref_issues)
        except Exception as exc:
            self.skipTest(f"Word COM runtime unavailable: {exc}")
        finally:
            try:
                if doc is not None:
                    doc.Close(False)
            except Exception:
                pass
            try:
                if word is not None:
                    word.Quit()
            except Exception:
                pass


if __name__ == "__main__":
    unittest.main()
