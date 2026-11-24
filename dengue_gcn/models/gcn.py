import torch
from torch import nn
from torch.nn import functional as F


class GCNLayer(nn.Module):
    def __init__(self, hidden_size):
        super().__init__()
        self.linear = nn.Linear(hidden_size, hidden_size, bias=False)

    def forward(self, states, adjacency):
        messages = torch.matmul(adjacency, self.linear(states))
        return F.relu(messages + states)


class GCN(nn.Module):
    def __init__(self, hidden_size, layers):
        super().__init__()
        self.layers = nn.ModuleList(GCNLayer(hidden_size) for _ in range(layers))

    def forward(self, states, adjacency):
        for layer in self.layers:
            states = layer(states, adjacency)
        return states
