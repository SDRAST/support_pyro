
from . import TestPublisherImplementation, TestSubscriberImplementation
from .. import test_case_with_server

class TestSubscriberAsClient(test_case_with_server(
    TestPublisherImplementation
)):
    def setUp(self):
        self.sub = TestSubscriberImplementation(self.uri)

if __name__ == "__main__":
    unittest.main()
