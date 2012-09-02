# -*- coding: utf-8 -*-
from __future__ import with_statement
from contextlib import contextmanager
from datetime import datetime, timedelta
from functools import wraps
from inspect import getargspec

from attest import Tests, assert_hook, raises

from energy import Energy


suite = Tests()


@contextmanager
def time_traveler(energy):
    changed_time = [0]
    def T(time=None):
        if time is None:
            return changed_time[0]
        else:
            changed_time[0] = time
    def wrap(meth):
        @wraps(meth)
        def wrapped(*args, **kwargs):
            kwargs_with_time = kwargs.copy()
            kwargs_with_time['time'] = T()
            try:
                print meth.__name__, args, kwargs_with_time
                return meth(*args, **kwargs_with_time)
            except TypeError, e:
                if str(e).endswith('\'time\''):
                    return meth(*args, **kwargs)
                raise
        return wrapped
    # Patch methods that has 'time' parameter to use changed time instead of
    # real time.
    originals = {}
    for attr in dir(energy):
        val = getattr(energy, attr)
        try:
            spec = getargspec(val)
        except TypeError:
            continue
        if 'time' not in spec[0]:
            continue
        originals[attr] = val
        setattr(energy, attr, wrap(val))
    yield (energy, T)
    # Revert changes
    for attr, meth in originals.iteritems():
        setattr(energy, attr, meth)


@suite.test
def init_energy():
    energy = Energy(10, 10)
    assert isinstance(energy.recovery_interval, int)
    assert energy.recovery_interval == 10
    energy = Energy(10, timedelta(seconds=10))
    assert isinstance(energy.recovery_interval, (int, float))
    assert energy.recovery_interval == 10


@suite.test
def use_energy():
    energy = Energy(10, 1000)
    assert energy == 10
    energy.use()
    assert energy == 9
    energy.use(5)
    assert energy == 4
    with raises(ValueError):
        energy.use(5)


@suite.test
def set_energy():
    energy = Energy(10, 1000)
    energy.set(1)
    assert energy == 1
    energy.set(5)
    assert energy == 5


@suite.test
def reset_energy():
    energy = Energy(10, 1000)
    energy.use(5)
    assert energy == 5
    energy.reset()
    assert energy == 10


@suite.test
def cast_energy():
    true_energy = Energy(1, 1000)
    false_energy = Energy(0, 1000)
    assert int(true_energy) == 1
    assert int(false_energy) == 0
    assert float(true_energy) == 1.0
    assert float(false_energy) == 0.0
    assert bool(true_energy) is True
    assert bool(false_energy) is False


@suite.test
def recover_energy():
    with time_traveler(Energy(10, 5)) as (energy, T):
        T( 0); energy.use(1)
        T( 1); assert energy == 9;  assert energy.recover_in() == 4
        T( 2); assert energy == 9;  assert energy.recover_in() == 3
        T( 3); assert energy == 9;  assert energy.recover_in() == 2
        T( 4); assert energy == 9;  assert energy.recover_in() == 1
        T( 5); assert energy == 10; assert energy.recover_in() == 0
        T( 6); assert energy == 10; assert energy.recover_in() == 0
        T(99); assert energy == 10; assert energy.recover_in() == 0


@suite.test
def use_energy_while_recovering():
    with time_traveler(Energy(10, 5)) as (energy, T):
        T( 0); energy.use(5)
        T( 1); assert energy == 5
        T( 2); energy.use(1)
        T( 3); assert energy == 4
        T( 4); assert energy == 4
        T( 5); assert energy == 5
        T( 6); assert energy == 5
        T( 7); energy.use(1)
        T( 8); assert energy == 4
        T( 9); assert energy == 4
        T(10); assert energy == 5


@suite.test
def use_energy_after_recovered():
    with time_traveler(Energy(10, 5)) as (energy, T):
        T( 0); energy.use(10)
        T( 1); assert energy == 0
        T( 5); energy.use(1)
        T( 6); assert energy == 0


@suite.test
def use_energy_in_the_future():
    with time_traveler(Energy(10, 5)) as (energy, T):
        T( 5); energy.use()
        T( 6); assert energy.passed() == 1
        with raises(ValueError):
            T( 0); energy.passed()


@suite.test
def pickle_energy():
    try:
        import cPickle as pickle
    except ImportError:
        import pickle
    with time_traveler(Energy(10, 5)) as (energy, T):
        T( 0); assert energy == 10
        T( 1); energy.use(5)
        T( 2); assert energy == 5
        dump = pickle.dumps(energy)
    with time_traveler(pickle.loads(dump)) as (energy, T):
        T( 3); assert energy == 5


@suite.test
def float_recovery_interval():
    with time_traveler(Energy(10, 0.5)) as (energy, T):
        T( 0); energy == 10
        T( 1); energy.use(3)
        T( 2); energy == 9
        T( 3); energy == 10


@suite.test
def equivalent_energy():
    assert Energy(10, 10) == Energy(10, 10)
    assert Energy(5, 10) != Energy(10, 10)
    e1, e2 = Energy(10, 10), Energy(10, 10)
    e1.use(time=123)
    e2.use(time=123)
    assert e1 == e2
    e1.use(time=128)
    assert e1 != e2


@suite.test
def set_max_energy():
    with time_traveler(Energy(10, 300)) as (energy, T):
        T( 0); assert energy == 10
        T( 1); energy.set_max(11)
        T( 2); assert energy == 11
        T( 3); energy.use()
        T( 4); assert energy == 10
        T( 5); energy.set_max(12)
        T( 6); assert energy == 10
        T( 7); energy.set_max(9)
        T( 8); assert energy == 9
        T( 9); energy.set_max(1)
        T(10); assert energy == 1
        T(11); energy.set_max(10)
        T(12); assert energy == 10
