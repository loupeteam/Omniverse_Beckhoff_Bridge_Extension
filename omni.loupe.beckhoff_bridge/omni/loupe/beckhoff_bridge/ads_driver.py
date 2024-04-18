import pyads
import time

structure_def = (
    ('var1', pyads.PLCTYPE_BOOL, 1),
    ('var_array', pyads.PLCTYPE_UDINT, 100)
)

class AdsDriver():

    def __init__(self):     
        self._connection = pyads.Connection('39.163.103.49.1.1', pyads.PORT_TC3PLC1)
        self._connection.open()
        self._structure_handle = self._connection.get_handle("MAIN.custom_struct")

    def read_structure(self):
        data = self._connection.read_structure_by_name('', structure_def, handle=self._structure_handle)
        return data

