from abc import ABC, abstractmethod

# create abstract class for event
class EventProcessor(ABC):

    def __init__(self, settings):
        self.settings = settings

    @abstractmethod
    def process(self, payload):
        pass