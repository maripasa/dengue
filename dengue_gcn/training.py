import math
import random
import time

import torch
from torch import nn

from .config import BATCH_SIZE, MAX_EPOCHS, PATIENCE, SEED
from .data import make_examples
from .models.lstm_gcn import LSTMGCN


@torch.no_grad()
def evaluate(model, examples, adjacency, span):
    if model is not None:
        model.eval()
    absolute_error = squared_error = nonzero_error = large_error = 0.0
    observations = nonzero_observations = large_observations = 0
    for start in range(span.start, span.stop, BATCH_SIZE):
        batch = slice(start, min(start + BATCH_SIZE, span.stop))
        prediction = examples.last[batch] if model is None else model(
            examples.x[batch], examples.last[batch], adjacency
        ).clamp_min(0)
        target = examples.target[batch]
        errors = (prediction - target).abs()
        nonzero = target > 0
        large = target >= 10
        absolute_error += errors.sum().item()
        squared_error += errors.square().sum().item()
        nonzero_error += errors[nonzero].sum().item()
        large_error += errors[large].sum().item()
        observations += errors.numel()
        nonzero_observations += nonzero.sum().item()
        large_observations += large.sum().item()
    return {
        "mae": absolute_error / observations,
        "rmse": math.sqrt(squared_error / observations),
        "mae_nonzero": nonzero_error / nonzero_observations,
        "mae_ge10": large_error / large_observations,
        "observations": observations,
        "nonzero_observations": nonzero_observations,
        "ge10_observations": large_observations,
    }


def fit(config, data, spans, device, output):
    random.seed(SEED)
    torch.manual_seed(SEED)
    if device.type == "cuda":
        torch.cuda.manual_seed_all(SEED)
    examples = make_examples(data, config.lookback, config.seasonal).to(device)
    adjacency = data.adjacency.to(device)
    model = LSTMGCN(config).to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=config.learning_rate, weight_decay=1e-4)
    loss_function = nn.SmoothL1Loss(beta=10.0)
    checkpoint = output / "checkpoints" / f"{config.id:03d}.pt"
    checkpoint.parent.mkdir(parents=True, exist_ok=True)
    best_validation = evaluate(model, examples, adjacency, spans["validation"])
    best_epoch = 0
    torch.save(model.state_dict(), checkpoint)
    stale_epochs = 0
    started = time.monotonic()
    for epoch in range(1, MAX_EPOCHS + 1):
        model.train()
        order = torch.randperm(spans["train"].stop, device=device)
        for start in range(0, len(order), BATCH_SIZE):
            indices = order[start:start + BATCH_SIZE]
            optimizer.zero_grad(set_to_none=True)
            prediction = model(examples.x[indices], examples.last[indices], adjacency)
            loss = loss_function(prediction, examples.target[indices])
            loss.backward()
            nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
        validation = evaluate(model, examples, adjacency, spans["validation"])
        if validation["mae"] < best_validation["mae"] - 1e-6:
            best_validation = validation
            best_epoch = epoch
            stale_epochs = 0
            torch.save(model.state_dict(), checkpoint)
        else:
            stale_epochs += 1
            if stale_epochs >= PATIENCE:
                break
    return {
        "config": config.as_dict(),
        "best_epoch": best_epoch,
        "epochs_ran": epoch,
        "validation": best_validation,
        "seconds": round(time.monotonic() - started, 2),
        "checkpoint": str(checkpoint.relative_to(output)),
    }


def test_checkpoint(config, checkpoint, data, spans, device):
    examples = make_examples(data, config.lookback, config.seasonal).to(device)
    adjacency = data.adjacency.to(device)
    model = LSTMGCN(config).to(device)
    model.load_state_dict(torch.load(checkpoint, map_location=device, weights_only=True))
    return evaluate(model, examples, adjacency, spans["test"])
