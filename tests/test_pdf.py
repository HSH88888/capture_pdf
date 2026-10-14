"""PDF 저장 기능 기본 테스트 (화면 캡처 없이 실행 가능)."""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PIL import Image  # noqa: E402

from capture_pdf import save_images_as_pdf, unique_pdf_path  # noqa: E402


class PdfTest(unittest.TestCase):
    def test_single_page(self):
        with tempfile.TemporaryDirectory() as d:
            path = save_images_as_pdf([Image.new("RGBA", (800, 600), "red")],
                                      unique_pdf_path(d))
            with open(path, "rb") as f:
                data = f.read()
            self.assertTrue(data.startswith(b"%PDF"))
            self.assertEqual(data.count(b"/Type /Page\n"), 1)

    def test_multi_page(self):
        with tempfile.TemporaryDirectory() as d:
            images = [Image.new("RGB", (300, 200), c) for c in ("red", "green", "blue")]
            path = save_images_as_pdf(images, unique_pdf_path(d))
            with open(path, "rb") as f:
                self.assertEqual(f.read().count(b"/Type /Page\n"), 3)

    def test_unique_path_does_not_overwrite(self):
        with tempfile.TemporaryDirectory() as d:
            first = unique_pdf_path(d)
            open(first, "wb").close()
            self.assertNotEqual(first, unique_pdf_path(d))


if __name__ == "__main__":
    unittest.main()
