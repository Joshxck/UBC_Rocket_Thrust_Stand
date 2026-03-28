import collections

class MovingAverageFilter:
    def __init__(self, size=2):
        self.buffer = collections.deque(maxlen=size)

    def update(self, sample):
        self.buffer.append(sample)
        return sum(self.buffer) / len(self.buffer)

class LeakyIntegrator:
    def __init__(self, alpha=0.9):
        self.alpha = alpha
        self.state = 0.0

    def update(self, sample):
        self.state = self.alpha * self.state + (1 - self.alpha) * sample
        return self.state