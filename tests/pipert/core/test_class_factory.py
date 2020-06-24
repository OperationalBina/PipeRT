import pytest

from pipert.core.class_factory import ClassFactory
from tests.pipert.core.utils.routines.dummy_routine import DummyRoutine


def test_class_factory_with_valid_path():
    routines_factory = ClassFactory("tests/pipert/core/utils/routines")
    assert DummyRoutine is routines_factory.get_class("DummyRoutine")


def test_class_factory_with_invalid_path():
    routines_factory = ClassFactory("tests/pipert/core/utils/routins")
    assert routines_factory.get_class("DummyRoutine") is None


def test_class_factory_with_invalid_class_name():
    routines_factory = ClassFactory("tests/pipert/core/utils/routines")
    assert routines_factory.get_class("NoCLass") is None
