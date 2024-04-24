import carb.events
import omni.kit.app

EVENT_TYPE_DATA_INIT = carb.events.type_from_string("loupe.beckhoff_bridge.DATA_INIT")
EVENT_TYPE_DATA_READ = carb.events.type_from_string("loupe.beckhoff_bridge.DATA_READ")
EVENT_TYPE_DATA_READ_REQ = carb.events.type_from_string("loupe.beckhoff_bridge.DATA_READ_REQ")
EVENT_TYPE_DATA_WRITE_REQ = carb.events.type_from_string("loupe.beckhoff_bridge.DATA_WRITE_REQ")

class BeckhoffBridge:
    def __init__( self ):
        self._event_stream = omni.kit.app.get_app().get_message_bus_event_stream()
        self._callbacks = []

    def __del__(self):
        for callback in self._callbacks:
            self._event_stream.remove_subscription(callback)

    def register_init_callback(self, callback):
        self._callbacks.append(self._event_stream.create_subscription_to_push_by_type(EVENT_TYPE_DATA_INIT, callback))        
        callback( None )

    def register_data_callback(self, callback):
        self._callbacks.append(self._event_stream.create_subscription_to_push_by_type(EVENT_TYPE_DATA_READ, callback))       

    def add_cyclic_read_variables(self, variableList):
        self._event_stream.push(event_type=EVENT_TYPE_DATA_READ_REQ, payload={'variables':variableList})

    def write_variable(self, name, value):
        payload = {"variables":[{'name': name, 'value': value}]}
        self._event_stream.push(event_type=EVENT_TYPE_DATA_WRITE_REQ, payload=payload)
