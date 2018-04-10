from .metric import Metric
from .aggregate import Aggregate
from .histogram import Histogram
from .event import Event
from .distribution import Distribution


available_metrics = {
    'metric': Metric,
    'aggregate': Aggregate,
    'histogram': Histogram,
    'event': Event,
    'distribution': Distribution
}