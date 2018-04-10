from datauploader.common.interfaces import AbstractClient

import io
import os
import logging
import json

logger = logging.getLogger(__name__)


class LocalStorageClient(AbstractClient):
    separator = '\t'

    def __init__(self, meta, job):
        super(LocalStorageClient, self).__init__(meta, job)
        self.file_streams = {}

    def __create_artifact(self, metric):
        self.file_streams[metric.local_id] = io.open(
            os.path.join(
                self.job.artifacts_dir, "{id}.data".format(id=metric.local_id)
            ),
            mode='wb'
        )

    def put(self, df, metric):
        if metric.local_id not in self.file_streams:
            logger.debug('Creating artifact file for %s', metric.local_id)
            self.__create_artifact(metric)
            dtypes = {}
            for name, type_ in metric.dtypes.items():
                dtypes[name] = type_.__name__
            header = json.dumps({'type': metric.type, 'names': metric.columns, 'dtypes': dtypes})
            self.file_streams[metric.local_id].write("%s\n" % header)
        data = df.to_csv(
            sep=self.separator,
            header=False,
            index=False,
            columns=metric.columns
        )
        logger.debug('writing report data: %s', data)
        self.file_streams[metric.local_id].write(data)
        self.file_streams[metric.local_id].flush()

    def close(self):
        for file_ in self.file_streams:
            self.file_streams[file_].close()
