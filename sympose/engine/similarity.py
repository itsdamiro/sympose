"""The scan behind the search by meaning (docs/decisions/027): the similarity of a message to
every passage. One matrix product when numpy is installed, a plain loop when it is not; both give
the same answer to within float rounding. Nothing to configure: numpy is used if it can be imported."""

from array import array
from typing import Sequence

from sympose.engine import embeddings

try:
    import numpy
except ImportError:  # optional: `pip install "sympose[fast]"`
    numpy = None


class VectorSet:
    """The unit vectors of a list of passages, and their similarity to a unit-length query."""

    def __init__(self, vectors: list[array]) -> None:
        self.dims = len(vectors[0]) if vectors else 0
        self._np = numpy  # the path this set was built for
        if self._np is not None and vectors:
            self._matrix = self._np.vstack([self._np.frombuffer(v, dtype=self._np.float32) for v in vectors])
            self._rows: list[array] = []
        else:
            self._matrix = None
            self._rows = vectors

    def note_set(self, codes: list[int], count: int) -> "VectorSet":
        """`count` vectors made from these rows (docs/decisions/066): row `i` belongs to the group `codes[i]`; each
        group becomes the mean of its rows, the mean of the groups' means is taken away from every one, and each is
        scaled to length one again. A group with no row, or whose vector is the average itself, stays all zeros."""
        if self._matrix is not None:
            np = self._np
            order = np.argsort(np.asarray(codes), kind="stable")
            sorted_codes = np.asarray(codes)[order]
            groups, starts = np.unique(sorted_codes, return_index=True)
            means = np.zeros((count, self._matrix.shape[1]), dtype=np.float32)
            means[groups] = np.add.reduceat(self._matrix[order], starts, axis=0) / np.diff(np.append(starts, len(order)))[:, None]
            centred = means - means[groups].mean(axis=0)
            norms = np.linalg.norm(centred, axis=1, keepdims=True)
            unit = centred / np.where(norms > 0, norms, 1.0)
            absent = np.ones(count, dtype=bool)
            absent[groups] = False
            unit[absent] = 0.0
            made = VectorSet([])
            made._np, made._matrix, made._rows, made.dims = np, unit.astype(np.float32), [], unit.shape[1]
            return made
        sums: dict[int, list[float]] = {}
        taken: dict[int, int] = {}
        for code, row in zip(codes, self._rows):
            sums[code] = [a + b for a, b in zip(sums[code], row)] if code in sums else [float(x) for x in row]
            taken[code] = taken.get(code, 0) + 1
        means = {code: [x / taken[code] for x in total] for code, total in sums.items()}
        centre = [sum(column) / len(means) for column in zip(*means.values())] if means else []
        return VectorSet([embeddings.unit([x - c for x, c in zip(means[code], centre)]) if code in means else array("f", [0.0] * len(centre)) for code in range(count)])

    def row(self, position: int) -> Sequence[float]:
        """The unit vector at `position`, in the order the set was given."""
        return self._matrix[position] if self._matrix is not None else self._rows[position]

    def scores(self, query: Sequence[float]) -> list[float]:
        """The cosine of `query` (unit length) with each vector, in the order they were given."""
        if self._matrix is not None:
            return (self._matrix @ self._np.asarray(query, dtype=self._np.float32)).tolist()
        return [embeddings.dot(query, row) for row in self._rows]
