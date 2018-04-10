import threading
import time
import pandas as pd
import logging

from netort.data_processing import get_nowait_from_queue

logger = logging.getLogger(__name__)


class MetricsRouter(threading.Thread):
    """
    Drain a queue and put its contents to list of destinations
    """

    def __init__(self, source, clients):
        super(MetricsRouter, self).__init__()
        self.source = source
        self.clients = clients
        self._finished = threading.Event()
        self._interrupted = threading.Event()
        self.setDaemon(True)  # just in case, bdk+ytank stuck w/o this at join of Drain thread
        self.data_buffer = {}
        self.metrics_buffer = {}

    def run(self):
        while not self._interrupted.is_set():
            self.data_buffer = {}
            self.metrics_buffer = {}
            data = get_nowait_from_queue(self.source)
            for df, metric in data:
                if metric.type in self.data_buffer:
                    # append df to existing buffer
                    self.data_buffer[metric.type] = pd.concat([self.data_buffer[metric.type], df])
                else:
                    # create buffer for new metric type
                    self.data_buffer[metric.type] = df
                    self.metrics_buffer[metric.type] = metric
                if self._interrupted.is_set():
                    break
            logger.debug('Buffer after routing: %s', self.data_buffer)
            for client in self.clients:
                for type_ in self.data_buffer:
                    client.put(self.data_buffer[type_], self.metrics_buffer[type_])

            if self._interrupted.is_set():
                break
            time.sleep(1)
        self._finished.set()

    def wait(self, timeout=None):
        self._finished.wait(timeout=timeout)

    def close(self):
        self._interrupted.set()