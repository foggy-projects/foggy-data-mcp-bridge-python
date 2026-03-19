"""Tuple utilities for multi-value returns.

Provides Tuple2 through Tuple8 for returning multiple values.
In Python, you can also use regular tuples or NamedTuple,
but these provide named access to elements.
"""

from dataclasses import dataclass
from typing import Generic, List, TypeVar

T1 = TypeVar("T1")
T2 = TypeVar("T2")
T3 = TypeVar("T3")
T4 = TypeVar("T4")
T5 = TypeVar("T5")
T6 = TypeVar("T6")
T7 = TypeVar("T7")
T8 = TypeVar("T8")


@dataclass
class Tuple2(Generic[T1, T2]):
    """A tuple of 2 elements."""

    _1: T1
    _2: T2

    def __iter__(self):
        yield self._1
        yield self._2

    def to_list(self) -> List:
        return [self._1, self._2]

    def __getitem__(self, index: int):
        return [self._1, self._2][index]


@dataclass
class Tuple3(Generic[T1, T2, T3]):
    """A tuple of 3 elements."""

    _1: T1
    _2: T2
    _3: T3

    def __iter__(self):
        yield self._1
        yield self._2
        yield self._3

    def to_list(self) -> List:
        return [self._1, self._2, self._3]


@dataclass
class Tuple4(Generic[T1, T2, T3, T4]):
    """A tuple of 4 elements."""

    _1: T1
    _2: T2
    _3: T3
    _4: T4

    def __iter__(self):
        yield self._1
        yield self._2
        yield self._3
        yield self._4

    def to_list(self) -> List:
        return [self._1, self._2, self._3, self._4]


@dataclass
class Tuple5(Generic[T1, T2, T3, T4, T5]):
    """A tuple of 5 elements."""

    _1: T1
    _2: T2
    _3: T3
    _4: T4
    _5: T5

    def __iter__(self):
        yield self._1
        yield self._2
        yield self._3
        yield self._4
        yield self._5

    def to_list(self) -> List:
        return [self._1, self._2, self._3, self._4, self._5]


@dataclass
class Tuple6(Generic[T1, T2, T3, T4, T5, T6]):
    """A tuple of 6 elements."""

    _1: T1
    _2: T2
    _3: T3
    _4: T4
    _5: T5
    _6: T6

    def __iter__(self):
        yield self._1
        yield self._2
        yield self._3
        yield self._4
        yield self._5
        yield self._6

    def to_list(self) -> List:
        return [self._1, self._2, self._3, self._4, self._5, self._6]


@dataclass
class Tuple7(Generic[T1, T2, T3, T4, T5, T6, T7]):
    """A tuple of 7 elements."""

    _1: T1
    _2: T2
    _3: T3
    _4: T4
    _5: T5
    _6: T6
    _7: T7

    def __iter__(self):
        yield self._1
        yield self._2
        yield self._3
        yield self._4
        yield self._5
        yield self._6
        yield self._7

    def to_list(self) -> List:
        return [self._1, self._2, self._3, self._4, self._5, self._6, self._7]


@dataclass
class Tuple8(Generic[T1, T2, T3, T4, T5, T6, T7, T8]):
    """A tuple of 8 elements."""

    _1: T1
    _2: T2
    _3: T3
    _4: T4
    _5: T5
    _6: T6
    _7: T7
    _8: T8

    def __iter__(self):
        yield self._1
        yield self._2
        yield self._3
        yield self._4
        yield self._5
        yield self._6
        yield self._7
        yield self._8

    def to_list(self) -> List:
        return [self._1, self._2, self._3, self._4, self._5, self._6, self._7, self._8]


class Tuples:
    """Factory methods for creating tuples."""

    @staticmethod
    def of2(_1: T1, _2: T2) -> Tuple2[T1, T2]:
        return Tuple2(_1=_1, _2=_2)

    @staticmethod
    def of3(_1: T1, _2: T2, _3: T3) -> Tuple3[T1, T2, T3]:
        return Tuple3(_1=_1, _2=_2, _3=_3)

    @staticmethod
    def of4(_1: T1, _2: T2, _3: T3, _4: T4) -> Tuple4[T1, T2, T3, T4]:
        return Tuple4(_1=_1, _2=_2, _3=_3, _4=_4)

    @staticmethod
    def of5(_1: T1, _2: T2, _3: T3, _4: T4, _5: T5) -> Tuple5[T1, T2, T3, T4, T5]:
        return Tuple5(_1=_1, _2=_2, _3=_3, _4=_4, _5=_5)

    @staticmethod
    def of6(_1: T1, _2: T2, _3: T3, _4: T4, _5: T5, _6: T6) -> Tuple6[T1, T2, T3, T4, T5, T6]:
        return Tuple6(_1=_1, _2=_2, _3=_3, _4=_4, _5=_5, _6=_6)

    @staticmethod
    def of7(_1: T1, _2: T2, _3: T3, _4: T4, _5: T5, _6: T6, _7: T7) -> Tuple7[T1, T2, T3, T4, T5, T6, T7]:
        return Tuple7(_1=_1, _2=_2, _3=_3, _4=_4, _5=_5, _6=_6, _7=_7)

    @staticmethod
    def of8(_1: T1, _2: T2, _3: T3, _4: T4, _5: T5, _6: T6, _7: T7, _8: T8) -> Tuple8[T1, T2, T3, T4, T5, T6, T7, T8]:
        return Tuple8(_1=_1, _2=_2, _3=_3, _4=_4, _5=_5, _6=_6, _7=_7, _8=_8)

    @staticmethod
    def from_list(items: List) -> Tuple2 | Tuple3 | Tuple4 | Tuple5 | Tuple6 | Tuple7 | Tuple8:
        """Create tuple from list."""
        n = len(items)
        if n == 2:
            return Tuple2(items[0], items[1])
        elif n == 3:
            return Tuple3(items[0], items[1], items[2])
        elif n == 4:
            return Tuple4(items[0], items[1], items[2], items[3])
        elif n == 5:
            return Tuple5(items[0], items[1], items[2], items[3], items[4])
        elif n == 6:
            return Tuple6(items[0], items[1], items[2], items[3], items[4], items[5])
        elif n == 7:
            return Tuple7(items[0], items[1], items[2], items[3], items[4], items[5], items[6])
        elif n == 8:
            return Tuple8(items[0], items[1], items[2], items[3], items[4], items[5], items[6], items[7])
        else:
            raise ValueError(f"Cannot create tuple from list of length {n}. Expected 2-8 elements.")