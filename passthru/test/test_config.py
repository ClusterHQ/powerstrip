# Copyright ClusterHQ Limited. See LICENSE file for details.

"""
Tests for ``powerstrip._config``.
"""

from twisted.trial.unittest import TestCase
from twisted.python.filepath import FilePath

from .._config import PluginConfiguration

class PluginConfigurationTests(TestCase):
    """
    Tests for ``PluginConfiguration``.
    """

    def setUp(self):
        self.config = PluginConfiguration()

    def test_read_from_yaml_file_success(self):
        """
        ``_read_from_yaml_file`` returns the file's content.
        """
        content = b"ducks: cows"
        fp = FilePath(self.mktemp())
        fp.setContent(content)

        result = self.config._read_from_yaml_file(fp)

        self.assertEquals(result, content)
