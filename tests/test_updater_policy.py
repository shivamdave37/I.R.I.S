"""Check the supervised updater's path boundary rules."""

import os
import unittest
from unittest.mock import patch

from updater import policy


class PolicyTests(unittest.TestCase):
    """Cover allowed, protected, and redirected update paths."""

    def test_tier_zero_paths_are_protected(self):
        """Every configured protected root path is classified as tier zero."""
        for path in policy.TIER0_FILES:
            with self.subTest(path=path):
                self.assertEqual(policy.check_path(path), "tier0")
        for folder in policy.TIER0_DIRS:
            with self.subTest(path=folder):
                self.assertEqual(policy.check_path(folder), "tier0")
                self.assertEqual(policy.check_path(folder + "/child.py"), "tier0")

    def test_tier_one_and_refused_paths(self):
        """Only listed existing-code shapes are offered as patch targets."""
        for path in ("main.py", "iris/iris.py", "skills/news.py"):
            with self.subTest(path=path):
                self.assertEqual(policy.check_path(path), "tier1")
        for path in ("../main.py", "iris/../main.py", "new.py", "data/foo.py", "skills/learned/a.py", ".git/config"):
            with self.subTest(path=path):
                self.assertEqual(policy.check_path(path), "refused")

    def test_symlink_component_is_refused(self):
        """A linked target cannot redirect a patch beyond its named path."""
        with patch.object(policy.os.path, "islink", side_effect=lambda path: path.endswith(os.sep + "main.py")):
            self.assertEqual(policy.check_path("main.py"), "refused")


if __name__ == "__main__":
    unittest.main()
