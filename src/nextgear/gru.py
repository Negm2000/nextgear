"""The learned model: a one-layer GRU over the raw event history."""

import copy
import math
import random

import numpy as np
import torch
from torch import nn
from torch.nn.utils.rnn import pack_padded_sequence, pad_packed_sequence, pad_sequence

from .events import INDEX, VOCAB


class _Network(nn.Module):
    def __init__(self, embedding: int, hidden: int):
        super().__init__()
        self.embed = nn.Embedding(len(VOCAB), embedding)
        self.gru = nn.GRU(embedding, hidden, batch_first=True)
        self.out = nn.Linear(hidden, len(VOCAB))

    def _packed(self, tokens, lengths):
        return pack_padded_sequence(self.embed(tokens), lengths.cpu(), batch_first=True, enforce_sorted=False)

    def forward(self, tokens: torch.Tensor, lengths: torch.Tensor) -> torch.Tensor:
        """Next-event logits after every position."""
        output, _ = pad_packed_sequence(self.gru(self._packed(tokens, lengths))[0], batch_first=True)
        return self.out(output)

    def last(self, tokens: torch.Tensor, lengths: torch.Tensor) -> torch.Tensor:
        """Next-event logits after the last real token of each sequence."""
        return self.out(self.gru(self._packed(tokens, lengths))[1][0])


def _tokens(sequences):
    inputs = [torch.tensor([INDEX[e] for e in s]) for s in sequences]
    return pad_sequence(inputs, batch_first=True), torch.tensor([len(x) for x in inputs])


def _batch(sequences):
    """Inputs are every event but the last; targets are every event but the first."""
    x, lengths = _tokens([s[:-1] for s in sequences])
    targets = pad_sequence([torch.tensor([INDEX[e] for e in s[1:]]) for s in sequences],
                           batch_first=True, padding_value=-100)
    return x, targets, lengths


def _loss(net, x, y, lengths, reduction="mean"):
    logits = net(x, lengths)
    return nn.functional.cross_entropy(logits.reshape(-1, len(VOCAB)), y[:, :logits.shape[1]].reshape(-1),
                                       ignore_index=-100, reduction=reduction)


class GRUModel:
    """Learns its own summary of the full history; no rules are built in."""

    def __init__(self, embedding: int = 32, hidden: int = 128, learning_rate: float = 3e-3,
                 batch_size: int = 64, max_epochs: int = 40, patience: int = 4, seed: int = 0):
        self.config = dict(embedding=embedding, hidden=hidden, learning_rate=learning_rate,
                           batch_size=batch_size, max_epochs=max_epochs, patience=patience, seed=seed)
        self.history: list[float] = []

    def validation_loss(self, sequences) -> float:
        self.net.eval()
        total, count = 0.0, 0
        with torch.no_grad():
            for start in range(0, len(sequences), 256):
                x, y, lengths = _batch(sequences[start:start + 256])
                total += float(_loss(self.net, x, y, lengths, reduction="sum"))
                count += int((y != -100).sum())
        return total / count

    # @cpt-algo:cpt-nextgear-algo-predictors-gru-train:p1
    def fit(self, train, validation) -> "GRUModel":
        cfg = self.config
        torch.manual_seed(cfg["seed"])
        order = random.Random(cfg["seed"])
        self.net = _Network(cfg["embedding"], cfg["hidden"])
        optimizer = torch.optim.Adam(self.net.parameters(), lr=cfg["learning_rate"])
        best, best_state, stale = math.inf, None, 0
        train = list(train)
        for _ in range(cfg["max_epochs"]):
            # @cpt-begin:cpt-nextgear-algo-predictors-gru-train:p1:inst-epoch
            self.net.train()
            order.shuffle(train)
            for start in range(0, len(train), cfg["batch_size"]):
                loss = _loss(self.net, *_batch(train[start:start + cfg["batch_size"]]))
                optimizer.zero_grad()
                loss.backward()
                nn.utils.clip_grad_norm_(self.net.parameters(), 1.0)
                optimizer.step()
            # @cpt-end:cpt-nextgear-algo-predictors-gru-train:p1:inst-epoch
            # @cpt-begin:cpt-nextgear-algo-predictors-gru-train:p1:inst-early-stop
            self.history.append(self.validation_loss(validation))
            if self.history[-1] < best - 1e-4:
                best, best_state, stale = self.history[-1], copy.deepcopy(self.net.state_dict()), 0
            else:
                stale += 1
                if stale >= cfg["patience"]:
                    break
            # @cpt-end:cpt-nextgear-algo-predictors-gru-train:p1:inst-early-stop
        # @cpt-begin:cpt-nextgear-algo-predictors-gru-train:p1:inst-restore
        self.net.load_state_dict(best_state)
        self.net.eval()
        return self
        # @cpt-end:cpt-nextgear-algo-predictors-gru-train:p1:inst-restore

    def predict_many(self, sequences) -> list[np.ndarray]:
        """Row t of each matrix is the distribution of event t + 1 given events 0..t."""
        results = []
        with torch.no_grad():
            for start in range(0, len(sequences), 256):
                chunk = sequences[start:start + 256]
                x, lengths = _tokens([s[:-1] for s in chunk])
                probabilities = torch.softmax(self.net(x, lengths), dim=-1).numpy()
                results.extend(probabilities[i, :lengths[i]].astype(np.float64) for i in range(len(chunk)))
        return results

    def predict_session(self, events) -> np.ndarray:
        return self.predict_many([tuple(events)])[0]

    def predict_next(self, prefixes) -> np.ndarray:
        rows = []
        with torch.no_grad():
            for start in range(0, len(prefixes), 512):
                rows.append(torch.softmax(self.net.last(*_tokens(prefixes[start:start + 512])), dim=-1).numpy())
        return np.concatenate(rows).astype(np.float64)

    def save(self, path) -> None:
        torch.save({"config": self.config, "state": self.net.state_dict(), "history": self.history}, path)

    @classmethod
    def load(cls, path) -> "GRUModel":
        data = torch.load(path, weights_only=True)
        model = cls(**data["config"])
        model.net = _Network(data["config"]["embedding"], data["config"]["hidden"])
        model.net.load_state_dict(data["state"])
        model.net.eval()
        model.history = list(data["history"])
        return model
