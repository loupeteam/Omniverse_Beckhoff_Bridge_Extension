"""
Kit tests for the thin Beckhoff extension: the driver registration and the
deprecated 0.2.x import path. The ADS driver itself is tested with plain
pytest in beckhoff_bridge/tests; the framework in Omni-Utils.
"""

import importlib
import sys
import warnings

import carb.settings
import omni.kit.test
from beckhoff_bridge import AdsDriver
from loupe.simulation.bridge import registry

from .. import extension

LEGACY_BUS = "/exts/loupe.simulation.bridge/legacyBusNames"


def _import_compat():
    """Import BeckhoffBridge afresh and return (module, warnings caught)."""
    sys.modules.pop("loupe.simulation.beckhoff_bridge.BeckhoffBridge", None)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        module = importlib.import_module("loupe.simulation.beckhoff_bridge.BeckhoffBridge")
    return module, caught


class TestRegistration(omni.kit.test.AsyncTestCase):
    async def test_driver_registered_on_startup(self):
        spec = registry.get("beckhoff")
        self.assertIsNotNone(spec)
        self.assertIs(spec.driver_class, AdsDriver)
        self.assertEqual(spec.namespace, "beckhoff")
        self.assertEqual(spec.legacy_namespace, "beckhoff_bridge")
        self.assertEqual([o.key for o in spec.options], ["AmsNetId"])
        self.assertEqual(spec.attribute("AmsNetId"), "beckhoff:AmsNetId")
        self.assertEqual(spec.legacy_attribute("AmsNetId"), "beckhoff_bridge:AmsNetId")

    async def test_builds_ads_driver_from_options(self):
        driver = registry.get("beckhoff").create_driver({"AmsNetId": "10.0.0.1.1.1"})
        self.assertIsInstance(driver, AdsDriver)
        self.assertEqual(driver.ams_net_id, "10.0.0.1.1.1")
        default = registry.get("beckhoff").create_driver({})
        self.assertEqual(default.ams_net_id, "127.0.0.1.1.1")

    async def test_unregister_leaves_a_foreign_registration(self):
        class Other(AdsDriver):
            pass

        try:
            registry.register("beckhoff", Other, extension.OPTIONS)
            extension.unregister()
            self.assertIs(registry.get("beckhoff").driver_class, Other)
        finally:
            extension.register()
        self.assertIs(registry.get("beckhoff").driver_class, AdsDriver)


class TestCompatModule(omni.kit.test.AsyncTestCase):
    async def test_import_warns(self):
        _, caught = _import_compat()
        self.assertTrue(any(issubclass(w.category, DeprecationWarning) and "BeckhoffBridge" in str(w.message)
                            for w in caught), [str(w.message) for w in caught])

    async def test_reexports(self):
        import loupe.simulation.bridge as bridge
        module, _ = _import_compat()
        self.assertIs(module.get_system, bridge.get_system)
        self.assertEqual(module.EVENT_TYPE_DATA_READ, "loupe.simulation.beckhoff_bridge.DATA_READ")
        self.assertEqual(module.EVENT_TYPE_DATA_WRITE_REQ, "loupe.simulation.beckhoff_bridge.DATA_WRITE_REQ")
        self.assertEqual(module.Manager_Events.EVENT_TYPE_STATUS, "loupe.simulation.beckhoff_bridge.STATUS")
        self.assertTrue(issubclass(module.Manager, bridge.Manager))

    async def test_manager_on_legacy_names(self):
        module, _ = _import_compat()
        manager = module.Manager("PLC1")
        try:
            self.assertEqual(manager._events.EVENT_TYPE_DATA_READ, "loupe.simulation.beckhoff_bridge.DATA_READ")
        finally:
            manager.cleanup()

    async def test_manager_neutral_when_legacy_bus_off(self):
        module, _ = _import_compat()
        settings = carb.settings.get_settings()
        settings.set(LEGACY_BUS, False)
        try:
            manager = module.Manager("PLC1")
            self.assertEqual(manager._events.EVENT_TYPE_DATA_READ, "loupe.simulation.bridge.DATA_READ")
            manager.cleanup()
        finally:
            settings.set(LEGACY_BUS, True)

    async def test_no_name_manager_removed(self):
        module, _ = _import_compat()
        with self.assertRaises(ValueError):
            module.Manager()
