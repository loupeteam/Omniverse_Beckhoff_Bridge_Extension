import pyads

class AdsDriver():

    def __init__(self, ams_net_id):             

        self.ams_net_id = ams_net_id
        self._read_names = list()
        self._read_struct_def = dict()

    def add_read(self, name : str, structure_def = None):

        if(name not in self._read_names):
            self._read_names.append(name)

        if structure_def is not None:
            if name not in self._read_struct_def:
                self._read_struct_def[name] = structure_def

    def write_data(self, data : dict ):
        self._connection.write_list_by_name( data )

    def read_data(self):
        # self._connection.
        if self._read_names.__len__() > 0:
            data = self._connection.read_list_by_name( self._read_names, structure_defs=self._read_struct_def)
            parsed_data = dict()
            for name in data.keys():
                parsed_data = self._parse_name(parsed_data, name, data[name])
        else:
            parsed_data = dict()        
        return parsed_data
        
    def _parse_name(self, name_dict, name, value):
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
    
    def connect(self):
        self._connection = pyads.Connection(self.ams_net_id, pyads.PORT_TC3PLC1)
        self._connection.open()        


