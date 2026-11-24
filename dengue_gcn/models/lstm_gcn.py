from torch import nn

from .gcn import GCN
from .lstm import MunicipalityLSTM


class LSTMGCN(nn.Module):
    def __init__(self, config):
        super().__init__()
        input_size = 1 + {"none": 0, "week": 2, "week_month": 4}[config.seasonal]
        self.lstm = MunicipalityLSTM(input_size, config.hidden, config.lstm_layers)
        self.gcn = GCN(config.hidden, config.gcn_layers)
        self.output = nn.Linear(config.hidden, 1)
        nn.init.zeros_(self.output.weight)
        nn.init.zeros_(self.output.bias)

    def forward(self, x, last_counts, adjacency):
        states = self.lstm(x)
        connected_states = self.gcn(states, adjacency)
        correction = self.output(connected_states).squeeze(-1)
        return last_counts + correction
