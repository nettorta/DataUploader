import queue
import uuid


class AbstractClient(object):
    def __init__(self, meta, job):
        self.pending_metrics = []
        self.job = job
        self.pending_queue = queue.Queue()
        self.meta = meta

    def subscribe(self, metric):
        self.pending_metrics.append(metric)

    def put(self, df, metric):
        self.pending_queue.put((df, metric))


class AbstractMetric(object):
    def __init__(self, meta, queue_):
        self.local_id = "metric_{uuid}".format(uuid=uuid.uuid4())
        self.dtypes = {}
        self.meta = meta
        self.routing_queue = queue_
        self.columns = []

    @property
    def type(self):
        raise NotImplementedError('Abstract type property should be redefined!')

    def put(self, df):
        # FIXME we want assert w/ dtypes here
        self.routing_queue.put((df, self))
