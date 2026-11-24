from torch import nn


class MunicipalityLSTM(nn.Module):
    def __init__(self, input_size, hidden_size, layers):
        super().__init__()
        self.recurrent = nn.LSTM(
            input_size, hidden_size, num_layers=layers, batch_first=True,
            dropout=0.1 if layers > 1 else 0.0,
        )

    def forward(self, x):
        batch, municipalities, lookback, features = x.shape
        sequences = x.reshape(batch * municipalities, lookback, features)
        _, (hidden, _) = self.recurrent(sequences)
        return hidden[-1].reshape(batch, municipalities, -1)
