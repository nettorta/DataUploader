from datauploader.common.interfaces import AbstractClient
from datauploader.common.util import pretty_print
from retrying import retry, RetryError

import pkg_resources
import logging
import requests
import threading
import time
import queue
import datetime
import os

requests.packages.urllib3.disable_warnings()

logger = logging.getLogger(__name__)


RETRY_ARGS = dict(
    wrap_exception=True,
    stop_max_delay=10000,
    wait_fixed=1000,
    stop_max_attempt_number=5
)


@retry(**RETRY_ARGS)
def send_chunk(session, req, timeout=5):
    r = session.send(req, verify=False, timeout=timeout)
    r.raise_for_status()
    return r


class LunaClient(AbstractClient):
    metric_registration = '/create_metric/'
    metric_upload = '/upload_metric/'
    job_registration = '/create_job/'
    dbname = 'luna'

    def __init__(self, meta, job):
        super(LunaClient, self).__init__(meta, job)
        self.public_ids = {}
        self.luna_columns = ['key_date', 'tag']
        self.key_date = "{key_date}".format(key_date=datetime.datetime.now().strftime("%Y-%m-%d"))
        self.register_worker = RegisterWorkerThread(self)
        self.register_worker.start()
        self.worker = WorkerThread(self)
        self.worker.start()
        self.session = requests.session()

        self._job_number = None
        if self.meta.get('api_address'):
            self.api_address = self.meta.get('api_address')
        else:
            raise RuntimeError('Api address SHOULD be specified')

    @property
    def job_number(self):
        if not self._job_number:
            self._job_number = self.create_job()
            self.__test_id_link_to_jobno()
            return self._job_number
        else:
            return self._job_number

    def create_job(self):
        try:
            my_user_agent = pkg_resources.require('datauploader')[0].version
        except pkg_resources.DistributionNotFound:
            my_user_agent = 'Unknown'
        finally:
            headers = {
                "Content-Type": "application/json",
                "User-Agent": "{upward_ua}, Uploader/{uploader_ua}".format(
                    upward_ua=self.meta.get('user_agent', 'Unknown'),
                    uploader_ua=my_user_agent
                )
            }
        req = requests.Request(
            'POST',
            "{api_address}{path}".format(
                api_address=self.api_address,
                path=self.job_registration
            ),
            headers=headers
        )
        req.json = {
            'test_start': self.job.test_start
        }
        prepared_req = req.prepare()
        logger.debug('Prepared create_job request:\n%s', pretty_print(prepared_req))

        try:
            response = send_chunk(self.session, prepared_req)
        except RetryError:
            logger.warning('Failed to create luna job', exc_info=True)
            raise
        else:
            logger.debug('Luna create job status: %s', response.status_code)
            logger.debug('Answ data: %s', response.json())
            if not response.json().get('job'):
                logger.warning('Create job answ data: %s', response.json())
                raise ValueError('Luna returned answer without jobid: %s', response.json())
            else:
                return response.json().get('job')

    def __test_id_link_to_jobno(self):
        link_dir = os.path.join(self.job.artifacts_base_dir, 'luna')
        if not os.path.exists(link_dir):
            os.makedirs(link_dir)
        try:
            os.symlink(
                os.path.join(
                    os.path.relpath(self.job.artifacts_base_dir, link_dir), self.job.job_id
                ),
                os.path.join(link_dir, str(self.job_number))
            )
        except OSError:
            logger.warning('Unable to create symlink for test: %s', self.job.job_id)
        else:
            logger.debug('Symlink created for job: %s', self.job.job_id)

    def close(self):
        self.__test_id_link_to_jobno()
        self.register_worker.stop()
        self.register_worker.join()
        self.worker.stop()
        self.worker.join()


class RegisterWorkerThread(threading.Thread):
    """ Register metrics metadata, get public_id from luna and create map local_id <-> public_id """
    def __init__(self, client):
        super(RegisterWorkerThread, self).__init__()
        self._finished = threading.Event()
        self._interrupted = threading.Event()
        self.client = client
        self.session = requests.session()

    def run(self):
        while not self._interrupted.is_set():
            for metric in self.client.pending_metrics:
                tag = self.register_metric(metric)
                if not tag:
                    logger.warning('No public id returned for metric.local_id: %s', metric.local_id)
                elif tag in self.client.public_ids.values():
                    logger.warning(
                        'Tag %s for metric.local_id: %s is already in public_ids list! '
                        'Should be unique!', tag, metric.local_id
                    )
                else:
                    logger.debug('Successfully received tag %s for metric.local_id: %s', tag, metric.local_id)
                    self.client.public_ids[metric.local_id] = tag
                    # now we have public id for this metric, so remove it from pending metrics
                    del(self.client.pending_metrics[
                            self.client.pending_metrics.index(metric)
                    ])
            time.sleep(1)
        logger.info('Metric registration thread interrupted!')
        self._finished.set()

    def register_metric(self, metric):
        req = requests.Request(
            'POST',
            "{api_address}{path}".format(
                api_address=self.client.api_address,
                path=self.client.metric_registration
            ),
            headers = {"Content-Type": "application/json"}
        )
        req.json = {
            'job': self.client.job_number,
            'type': metric.type,
            'local_id': metric.local_id
        }
        for meta_key, meta_value in metric.meta.items():
            req.json[meta_key] = meta_value
        prepared_req = req.prepare()
        logger.debug('Prepared create_job request:\n%s', pretty_print(prepared_req))
        response = send_chunk(self.session, prepared_req)
        return response.json()['uniq_id']

    def is_finished(self):
        return self._finished

    def stop(self):
        logger.info('Metric registration thread get interrupt signal')
        self._interrupted.set()


class WorkerThread(threading.Thread):
    """ Process data """
    def __init__(self, client):
        super(WorkerThread, self).__init__()
        self._finished = threading.Event()
        self._interrupted = threading.Event()
        self.client = client
        self.session = requests.session()

    def run(self):
        while not self._interrupted.is_set():
            self.__process_pending_queue()
        logger.info('Luna uploader thread main loop interrupted, '
                    'finishing work and trying to send the rest of data, qsize: %s',
                    self.client.pending_queue.qsize())
        self.__process_pending_queue()
        self._finished.set()

    def __process_pending_queue(self):
        try:
            chunk = self.client.pending_queue.get_nowait()
        except queue.Empty:
            time.sleep(0.1)
        else:
            if chunk:
                df, metric = chunk
                if metric.local_id in self.client.public_ids:
                    df.loc[:, 'key_date'] = self.client.key_date
                    df.loc[:, 'tag'] = self.client.public_ids[metric.local_id]
                    body = df.to_csv(
                        sep='\t',
                        header=False,
                        index=False,
                        na_rep="",
                        columns=self.client.luna_columns + metric.columns
                    )
                    req = requests.Request(
                        'POST', "{api}{data_upload_handler}/?query={query}".format(
                            api=self.client.api_address,
                            data_upload_handler=self.client.metric_upload,
                            query="INSERT INTO {table} FORMAT TSV".format(
                                table="{db}.{type}".format(db=self.client.dbname, type=metric.type)
                            )
                        )
                    )
                    req.data = body
                    prepared_req = req.prepare()
                    logger.debug('Prepared upload request:\n%s', pretty_print(prepared_req))
                    try:
                        send_chunk(self.session, prepared_req)
                    except RetryError:
                        logger.warning('failed to upload data to luna backend. Dropped data: %s', body, exc_info=True)
                        return
                else:
                    # no public_id yet, put it back
                    self.client.pending_queue.put(
                        (df, metric)
                    )

    def is_finished(self):
        return self._finished

    def stop(self):
        logger.info('Uploader got interrupt signal')
        self._interrupted.set()
