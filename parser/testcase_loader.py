# parser/testcase_loader.py
import os
from parser.testcase_parser import parse_testcase
from parser.dsl_models import TestCase

class TestCaseLoader:

    def __init__(self, testcase_dir: str):
        self.testcase_dir = testcase_dir

    def load(self, testcase_name: str) -> TestCase:
        """
        Load testcase from file and return TestCase object
        """
        if not testcase_name.endswith(".txt"):
            filename = f"{testcase_name}.txt"
        else:
            filename = testcase_name

        path = os.path.join(self.testcase_dir, filename)

        if not os.path.exists(path):
            raise FileNotFoundError(f"Testcase not found: {path}")

        with open(path, encoding="utf-8") as f:
            content = f.read()

        testcase = parse_testcase(content)

        # Ensure name consistency
        testcase.name = testcase_name.replace(".txt", "")
        return testcase
