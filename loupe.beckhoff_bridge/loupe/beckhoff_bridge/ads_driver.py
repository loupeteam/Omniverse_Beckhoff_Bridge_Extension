import pyads

class AdsDriver():
    """
    A class that represents an ADS driver. It contains a list of variables to read from the target device and provides methods to read and write data.

    Args:
        ams_net_id (str): The AMS Net ID of the target device.

    Attributes:
        ams_net_id (str): The AMS Net ID of the target device.
        _read_names (list): A list of names for reading data.
        _read_struct_def (dict): A dictionary that maps names to structure definitions.

    """

    def __init__(self, ams_net_id):             
        """
        Initializes an instance of the AdsDriver class.

        Args:
            ams_net_id (str): The AMS Net ID of the target device.

        """
        self.ams_net_id = ams_net_id
        self._read_names = list()
        self._read_struct_def = dict()

    def add_read(self, name : str, structure_def = None):
        """
        Adds a variable to the list of data to read.

        Args:
            name (str): The name of the data to be read. "my_struct.my_array[0].my_var"
            structure_def (optional): The structure definition of the data.

        """
        if(name not in self._read_names):
            self._read_names.append(name)

        if structure_def is not None:
            if name not in self._read_struct_def:
                self._read_struct_def[name] = structure_def

    def write_data(self, data : dict ):
        """
        Writes data to the target device.

        Args:
            data (dict): A dictionary containing the data to be written. 
            e.g.
            data = {'MAIN.b_Execute': False, 'MAIN.str_TestString': 'Goodbye World', 'MAIN.r32_TestReal': 54.321}

        """
        self._connection.write_list_by_name( data )

    def read_data(self):
        """
        Reads all variables from the cyclic read list.

        Returns:
            dict: A dictionary containing the parsed data.

        """
        if self._read_names.__len__() > 0:
            data = self._connection.read_list_by_name( self._read_names, structure_defs=self._read_struct_def)
            parsed_data = dict()
            for name in data.keys():
                parsed_data = self._parse_name(parsed_data, name, data[name])
        else:
            parsed_data = dict()        
        return parsed_data
        
    def _parse_name(self, name_dict, name, value):
        """
        Convert a variable from a flat name to a dictionary based structure.

        "my_struct.my_array[0].my_var: value" -> {"my_struct": {"my_array": [{"my_var": value}]}}

        Args:
            name_dict (dict): The dictionary to store the parsed data.
            name (str): The name of the data item.
            value: The value of the data item.

        Returns:
            dict: The updated name_dict.

        """
        name_parts = name.split(".")
        if len(name_parts) > 1:
            if name_parts[0] not in name_dict:
                name_dict[name_parts[0]] = dict()
            if "[" in name_parts[1]:
                array_name, index = name_parts[1].split("[")
                index = int(index[:-1])
                if array_name not in name_dict[name_parts[0]]:
                    name_dict[name_parts[0]][array_name] = []
                if index >= len(name_dict[name_parts[0]][array_name]):
                    name_dict[name_parts[0]][array_name].extend([None] * (index - len(name_dict[name_parts[0]][array_name]) + 1))
                name_dict[name_parts[0]][array_name][index] = self._parse_name(name_dict[name_parts[0]][array_name], "[" + str(index) + "]" + ".".join(name_parts[2:]), value)
            else:
                name_dict[name_parts[0]] = self._parse_name(name_dict[name_parts[0]], ".".join(name_parts[1:]), value)
        else:
            if "[" in name_parts[0]:
                array_name, index = name_parts[0].split("[")
                index = int(index[:-1])
                if index >= len(name_dict):
                    name_dict.extend([None] * (index - len(name_dict) + 1))
                name_dict[index] = value
                return name_dict[index]
            else:
                name_dict[name_parts[0]] = value
        return name_dict
    
    def connect(self, ams_net_id = None):
        """
        Connects to the target device.

        Args:
            ams_net_id (str): The AMS Net ID of the target device. This does not need to be provided if it was provided in the constructor and has not changed.

        """
        if ams_net_id is not None:
            self.ams_net_id = ams_net_id

        self._connection = pyads.Connection(self.ams_net_id, pyads.PORT_TC3PLC1)
        self._connection.open()


