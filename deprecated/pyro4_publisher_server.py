"""
As I have moved away from the messagebus Pyro4 paradigm (at least for the moment)
this module remains deprecated.
"""

from .pyro4_server import Pyro4Server

class Pyro4PublisherServer(Pyro4Server):

    def __init__(self, name, publisher_thread_class,
                            publisher_thread_kwargs={},
                            bus=None,
                            **kwargs):

        Pyro4Server.__init__(self, name, **kwargs)
        self.bus = bus
        self.publisher_thread_class = publisher_thread_class
        self.publisher_thread_kwargs = publisher_thread_kwargs
        self.publisher = self.publisher_thread_class(self, bus=self.bus, **self.publisher_thread_kwargs)
        self._publishing_started = False

    #@Pyro4.expose
    @property
    def publishing_started(self):
        return self._publishing_started

    #@Pyro4.expose
    def start_publishing(self):
        """
        Start publishing power meter readings
        Returns:
            None
        """
        if self._publishing_started:
            return
        self._publishing_started = True
        self.logger.info("Starting to publish power meter readings")

        if self.publisher.stopped():
            self.publisher = self.publisher_thread_class(self, bus=self.bus, **self.publisher_thread_kwargs)
            self.publisher.daemon = True

        self.publisher.start()

    #@Pyro4.expose
    def stop_publishing(self):
        """
        Stop the publisher.
        Returns:
            None
        """
        self.publisher.stop()
        self.publisher.join()
        self._publishing_started = False

    #@Pyro4.expose
    def pause_publshing(self):
        """
        Pause the publisher
        Returns:
            None
        """
        self.publisher.pause()

    #@Pyro4.expose
    def unpause_publishing(self):
        """
        Unpause the publisher
        Returns:
            None
        """
        self.publisher.unpause()
