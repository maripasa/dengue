from dataclasses import asdict, dataclass


LOOKBACKS = (4, 8, 16)
HIDDEN_SIZES = (16, 32)
LSTM_LAYERS = (1, 2)
SEASONAL_FEATURES = ("none", "week", "week_month")
LEARNING_RATES = (0.001, 0.0003)
GCN_LAYERS = (1, 2, 4)
FIRST_TARGET = max(LOOKBACKS)
MAX_EPOCHS = 20
PATIENCE = 5
BATCH_SIZE = 16
SEED = 42


@dataclass(frozen=True)
class Experiment:
    id: int
    lookback: int
    hidden: int
    lstm_layers: int
    seasonal: str
    learning_rate: float
    gcn_layers: int

    def as_dict(self):
        return asdict(self)
