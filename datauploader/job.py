from datauploader.clients import available_clients
from datauploader.metrics import available_metrics

import queue
import logging
import uuid
import datetime
import tempfile
import os

from router import MetricsRouter


logger = logging.getLogger(__name__)


class Job(object):
    artifacts_base_dir = './logs/'

    def __init__(self, meta):
        self.routing_queue = queue.Queue()
        self.job_id = "job_{uuid}".format(uuid=uuid.uuid4())
        self.test_start = meta.get('test_start', time.time())
        self.clients = []
        self.__create_clients(meta)
        self.router = MetricsRouter(self.routing_queue, self.clients)
        self.router.start()
        self._artifacts_dir = None

    def __create_clients(self, meta):
        [
            self.clients.append(
                available_clients[client_meta.get('type')](client_meta, self)
            )
            for client_meta in meta.get('clients')
        ]

    def get_metric(self, meta):
        """
        meta sample:
        {
            'type': 'metric',
            'name': 'cpu_usage',
            'hostname': 'localhost'
            'some_meta_key': 'some_meta_value'
        }
        """
        type_ = meta.get('type')
        if not type_:
            raise ValueError('Metric type should be defined.')

        if type_ in available_metrics:
            metric = available_metrics[type_](meta, self.routing_queue)
            # FIXME filter metric subscribtion for clients via 'filter' of meta information
            [client.subscribe(metric) for client in self.clients]
            return metric
        else:
            raise NotImplementedError('Unknown uploader metric type: %s' % type_)

    @property
    def artifacts_dir(self):
        if not self._artifacts_dir:
            dir_name = "{dir}/{id}".format(
                dir=self.artifacts_base_dir, id=self.job_id)
            if not os.path.isdir(dir_name):
                os.makedirs(dir_name)
            os.chmod(dir_name, 0o755)
            self._artifacts_dir = os.path.abspath(dir_name)
        return self._artifacts_dir


if __name__ == '__main__':
    import time
    import pandas as pd
    logging.basicConfig(level='DEBUG')
    job = Job(
        {
            'clients': [
                {
                    'type': 'luna',
                    'api_address': 'https://volta-back-testing.common-int.yandex-team.ru',
                    'user_agent': 'Tank Test',
                    'filter': []
                },
                {
                    'type': 'local_storage',
                }
            ],
            'test_start': time.time()
         }
    )
    logger.debug('Clients: %s', job.clients)

    metric_meta = {
        'type': 'metric',
        'name': 'cpu_usage',
        'hostname': 'localhost',
        'some_meta_key': 'some_meta_value'
    }

    metric_obj = job.get_metric(metric_meta)

    logger.debug('Metric: %s', metric_obj)

    time.sleep(3)
    df = pd.DataFrame([[123, "value_123"]], columns=['ts', 'value'])
    metric_obj.put(df)
    df2 = pd.DataFrame([[456, "value_456"]], columns=['ts', 'value'])
    metric_obj.put(df2)
    time.sleep(10)
    df = pd.DataFrame([[123, "value_123"]], columns=['ts', 'value'])
    metric_obj.put(df)
    df2 = pd.DataFrame([[456, "value_456"]], columns=['ts', 'value'])
    metric_obj.put(df2)
    time.sleep(10)

    [client.close() for client in job.clients]
    job.router.close()
