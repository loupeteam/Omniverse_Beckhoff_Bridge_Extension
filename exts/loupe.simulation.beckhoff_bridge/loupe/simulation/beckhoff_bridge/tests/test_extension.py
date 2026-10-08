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


def _import_compat(name="BeckhoffBridge"):
    """Import a deprecated module afresh and return (module, warnings caught)."""
    full = "loupe.simulation.beckhoff_bridge." + name
    sys.modules.pop(full, None)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        module = importlib.import_module(full)
    return module, caught


def _deprecations(caught, name):
    return [w for w in caught if issubclass(w.category, DeprecationWarning) and name in str(w.message)]


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


class TestOtherCompatModules(omni.kit.test.AsyncTestCase):
    async def test_communication_driver_import_warns(self):
        sys.modules.pop("loupe.simulation.beckhoff_bridge.Communication", None)
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            # the 0.2.x spelling, exactly
            from loupe.simulation.beckhoff_bridge.Communication import AdsReadError, CommunicationDriver
        self.assertTrue(_deprecations(caught, "Communication"), [str(w.message) for w in caught])
        self.assertIn("0.5", str(_deprecations(caught, "Communication")[0].message))
        self.assertIs(CommunicationDriver, AdsDriver)
        from beckhoff_bridge import AdsReadError as LibAdsReadError
        self.assertIs(AdsReadError, LibAdsReadError)
        self.assertEqual(CommunicationDriver("10.0.0.1.1.1").ams_net_id, "10.0.0.1.1.1")

    async def test_global_variables_import_warns(self):
        module, caught = _import_compat("global_variables")
        self.assertTrue(_deprecations(caught, "global_variables"), [str(w.message) for w in caught])
        self.assertEqual(module.ATTR_BECKHOFF_BRIDGE_AMS_NET_ID, "beckhoff_bridge:AmsNetId")
        self.assertEqual(module.ATTR_BECKHOFF_BRIDGE_READ_VARS, "beckhoff_bridge:Variables")
        self.assertEqual(module.default_beckoff_properties[module.ATTR_BECKHOFF_BRIDGE_REFRESH], 20)
