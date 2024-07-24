"""
Test a wide variety of inputs for parsing PLC representations of data into a dictionary
"""

import omni.kit.test
from loupe.simulation.beckhoff_bridge.ads_driver import AdsDriver

# pylint: disable=W0212

class TestParseNameSingleVar(omni.kit.test.AsyncTestCase):
    """Tests for single variable parsing."""

    # Run before every test
    async def setUp(self):
        AdsDriver('127.0.0.1.1')
        self.driver = AdsDriver('127.0.0.1.1')
        self.test_output_string = "correct: {correct}\nactual: {actual}\n\n"
        self.test_different_data_types = ["30", 30, -18935, 30.151535, True, False]

    def test_start_empty(self):
        """Empty dictionary is populated with single var."""
        starting_dict = {}
        value = 30
        input_name = "gVar"
        correct_output = {input_name: value}

        actual_output = self.driver._parse_flat_plc_var_to_dict(starting_dict, input_name, value)

        self.assertEqual(actual_output, 
                         correct_output, 
                         msg=self.test_output_string.format(correct=correct_output, actual=actual_output))


    def test_start_nonempty(self):
        """Non-empty dictionary is populated with second var."""
        starting_dict = {"gInt" : 7}
        value = 30
        input_name = "gOtherInt"

        for value in self.test_different_data_types:
            correct_output = {"gInt" : 7, input_name: value}

            actual_output = self.driver._parse_flat_plc_var_to_dict(starting_dict, input_name, value)
            
            self.assertEqual(actual_output, 
                            correct_output, 
                            msg=self.test_output_string.format(correct=correct_output, actual=actual_output))


    def test_overwrite(self):
        """Non-empty dictionary has a single var overwritten."""
        starting_dict = {"gVar" : 1}
        input_name = "gVar"

        for value in self.test_different_data_types:
            correct_output = {"gVar": value}
            actual_output = self.driver._parse_flat_plc_var_to_dict(starting_dict, input_name, value)

            self.assertEqual(actual_output, 
                            correct_output, 
                            msg=self.test_output_string.format(correct=correct_output, actual=actual_output))


    def test_overwrite_string_list(self):
        """Non-empty dictionary has a string list ovewritten with a different var type."""
        starting_dict = {"gArray" : ['a', 'b', 'c']}
        value = 30
        input_name = "gArray"
        correct_output = {"gArray": value}

        actual_output = self.driver._parse_flat_plc_var_to_dict(starting_dict, input_name, value)

        self.assertEqual(actual_output, 
                         correct_output, 
                         msg=self.test_output_string.format(correct=correct_output, actual=actual_output))

    def test_overwrite_struct(self):
        """Overwrite a struct with a different var type."""
        starting_dict = {"gStruct" : {'a': 1}}
        value = 30
        input_name = "gStruct"
        correct_output = {"gStruct": value}

        actual_output = self.driver._parse_flat_plc_var_to_dict(starting_dict, input_name, value)

        self.assertEqual(actual_output, 
                         correct_output, 
                         msg=self.test_output_string.format(correct=correct_output, actual=actual_output))


class TestParseNameSingleArray(omni.kit.test.AsyncTestCase):
    """Tests for single array parsing."""

    # Run before every test
    async def setUp(self):
        self.driver = AdsDriver('127.0.0.1.1')
        self.test_output_string = "correct: {correct}\nactual: {actual}\n\n"
        self.test_different_data_types = ["30", 30, -18935, 30.151535, True, False]
    
    def test_start_empty(self):
        """Add a list to an existing dictionary"""
        starting_dict = {}
        value = 30
        input_name = "gBool[2]"
        correct_output = {"gBool": [None, None, value]}

        actual_output = self.driver._parse_flat_plc_var_to_dict(starting_dict, input_name, value)

        self.assertEqual(actual_output, 
                         correct_output, 
                         msg=self.test_output_string.format(correct=correct_output, actual=actual_output))

    def test_start_nonempty(self):
        """Read a single element of a list, from a dict already containing data."""
        starting_dict = {"gInt" : 7}
        value = True
        input_name = "gBool[2]"
        correct_output = {"gInt" : 7, "gBool": [None, None, value]}

        actual_output = self.driver._parse_flat_plc_var_to_dict(starting_dict, input_name, value)

        self.assertEqual(actual_output, 
                         correct_output, 
                         msg=self.test_output_string.format(correct=correct_output, actual=actual_output))


    def test_exists_empty_list(self):
        """Read a single element of a list, whose reprsentation is currently an empty list."""
        starting_dict = {"gBool" : []}
        value = False
        input_name = "gBool[2]"
        correct_output = {"gBool": [None, None, value]}

        actual_output = self.driver._parse_flat_plc_var_to_dict(starting_dict, input_name, value)

        self.assertEqual(actual_output, 
                         correct_output, 
                         msg=self.test_output_string.format(correct=correct_output, actual=actual_output))
    
    def test_exists_short_list(self):
        """Read a single element of a list, whose reprsentation is currently a list that's too short."""
        starting_dict = {"gBool" : [False]}
        value = True
        input_name = "gBool[2]"
        correct_output = {"gBool": [False, None, value]}

        actual_output = self.driver._parse_flat_plc_var_to_dict(starting_dict, input_name, value)

        self.assertEqual(actual_output, 
                         correct_output, 
                         msg=self.test_output_string.format(correct=correct_output, actual=actual_output))

    def test_exists_right_size_list(self):
        """Read a single element of a list, whose representation is a list where requested index is the last element."""
        starting_dict = {"gInt" : [1, 2, 3]}
        value = 30
        input_name = "gInt[2]"
        correct_output = {"gInt": [1, 2, value]}

        actual_output = self.driver._parse_flat_plc_var_to_dict(starting_dict, input_name, value)

        self.assertEqual(actual_output, 
                         correct_output, 
                         msg=self.test_output_string.format(correct=correct_output, actual=actual_output))
    
    def test_exists_long_list(self):
        starting_dict = {"gBool" : [1, 2, 3, 4, 5]}
        value = 30
        input_name = "gBool[2]"
        correct_output = {"gBool": [1, 2, value, 4, 5]}

        actual_output = self.driver._parse_flat_plc_var_to_dict(starting_dict, input_name, value)

        self.assertEqual(actual_output, 
                         correct_output, 
                         msg=self.test_output_string.format(correct=correct_output, actual=actual_output))

    def test_exists_num(self):
        starting_dict = {"gBool" : 40}
        value = 30
        input_name = "gBool[2]"
        correct_output = {"gBool": [None, None, value]}

        actual_output = self.driver._parse_flat_plc_var_to_dict(starting_dict, input_name, value)

        self.assertEqual(actual_output, 
                         correct_output, 
                         msg=self.test_output_string.format(correct=correct_output, actual=actual_output))

    def test_exists_dict(self):
        starting_dict = {"gBool" : {'a' : 1}}
        value = 30
        input_name = "gBool[2]"
        correct_output = {"gBool": [None, None, value]}

        actual_output = self.driver._parse_flat_plc_var_to_dict(starting_dict, input_name, value)

        self.assertEqual(actual_output, 
                         correct_output, 
                         msg=self.test_output_string.format(correct=correct_output, actual=actual_output))



class TestParseNameMultipart(omni.kit.test.AsyncTestCase):
    """Tests for multi-part parsing."""

    # Run before every test
    async def setUp(self):
        self.driver = AdsDriver('127.0.0.1.1')
        self.test_output_string = "correct: {correct}\nactual: {actual}\n\n"
        self.test_different_data_types = ["30", 30, -18935, 30.151535, True, False]

    def test_top_struct(self):
        """Test writing to a global struct."""
        value = 30
        input_name = "myStruct.subStruct.var"
        correct_output = {  
            "myStruct": {
                "subStruct": {
                    "var": value
                    }
                }
            }
        
        actual_output = self.driver._parse_flat_plc_var_to_dict({}, input_name, value)

        self.assertEqual(actual_output, 
                         correct_output, 
                         msg=self.test_output_string.format(correct=correct_output, actual=actual_output))

    def test_program_level_struct(self):
        """Test writing to a struct inside of a program."""
        value = 30
        input_name = "Program.struct.var"
        correct_output = {
            "Program": {
                "struct": {
                    "var": value}
                }
            }
        actual_output = self.driver._parse_flat_plc_var_to_dict({}, input_name, value)
        
        self.assertEqual(actual_output, 
                         correct_output, 
                         msg=self.test_output_string.format(correct=correct_output, actual=actual_output))

    def test_program_array_member(self):
        """Test writing to a specific array inside a program"""
        value = 30
        array_size = 30
        input_name = "Program.array[29]"
        correct_output = {"Program": {"array" : [None] * array_size}}
        correct_output["Program"]["array"][array_size - 1] = value
        
        actual_output = self.driver._parse_flat_plc_var_to_dict({}, input_name, value)
        
        self.assertEqual(actual_output, 
                         correct_output, 
                         msg=self.test_output_string.format(correct=correct_output, actual=actual_output))


    def test_array_index_member_first(self):
        """Test writing to first member of an array"""
        value = 30
        actual_output = self.driver._parse_flat_plc_var_to_dict({}, "myArray[0].myVar", value)
        correct_output =  {
                        "myArray": 
                        [
                            {"myVar": value}
                        ]
                    }
                    
        self.assertEqual(actual_output, 
                         correct_output, 
                         msg=self.test_output_string.format(correct=correct_output, actual=actual_output))
        self.assertEqual(len(actual_output["myArray"]),
                         len(correct_output["myArray"]),
                         msg="Array length should not have changed")

    def test_array_index_member_nth(self):
        """Test writing to last member of an array."""
        value = 30
        actual_output = self.driver._parse_flat_plc_var_to_dict({}, "myArray[2].myVar", value)
        correct_output =  {
                        "myArray": 
                        [   None,
                            None,
                            {"myVar": value}
                        ]
                    }
        self.assertEqual(actual_output, 
                         correct_output, 
                         msg=self.test_output_string.format(correct=correct_output, actual=actual_output))
        self.assertEqual(len(actual_output["myArray"]),
                         len(correct_output["myArray"]),
                         msg="Array length should not have changed")

    def test_array_index_member_nth_existing_replace(self):
        """Test replacing second to last of an array."""
        starting_dict = {'myVar' : 1, "myArray": [1, 2, 3, 4]}
        value = 30
        actual_output = self.driver._parse_flat_plc_var_to_dict(starting_dict, "myArray[2].myVar", value)
        correct_output =  {
                            "myVar" : 1,
                                "myArray": 
                                [   1,
                                    2,
                                    {"myVar": value},
                                    4
                                ]
                        }
        self.assertEqual(actual_output, 
                         correct_output, 
                         msg=self.test_output_string.format(correct=correct_output, actual=actual_output))
        self.assertEqual(len(actual_output["myArray"]),
                         len(correct_output["myArray"]),
                         msg="Array length should not have changed")

    def test_structure_array_index_member(self):
        """Writing to a struct inside of an array, inside of a struct."""
        value = 30
        actual_output = self.driver._parse_flat_plc_var_to_dict({}, "myStruct.myArray[0].myVar", value)
        correct_output =  {
                        "myStruct": 
                        {
                            "myArray": 
                            [
                                {"myVar": value}
                            ]
                        }
                    }
        self.assertEqual(actual_output, 
                         correct_output, 
                         msg=self.test_output_string.format(correct=correct_output, actual=actual_output))
        self.assertEqual(len(actual_output["myStruct"]["myArray"]),
                         len(correct_output["myStruct"]["myArray"]),
                         msg="Array length should not have changed")
        
    def test_deep_array_inside_struct(self):
        """Writing to a deeply nested array inside of a struct."""
        correct_output =  {
                            "myStruct": 
                            {
                                "myStruct": 
                                {
                                    "myStruct": 
                                    {
                                        "myArray": 
                                        [
                                            None
                                        ]
                                    }
                                }
                            }
                        }
        # Global
        for value in self.test_different_data_types:
            actual_output = self.driver._parse_flat_plc_var_to_dict({}, "myStruct.myStruct.myStruct.myArray[0]", value)
            correct_output["myStruct"]["myStruct"]["myStruct"]["myArray"][0] = value
            self.assertEqual(actual_output, 
                            correct_output, 
                            msg=self.test_output_string.format(correct=correct_output, actual=actual_output))
        # Program
        correct_output =  {
                            "Program": 
                            {
                                "myStruct": 
                                {
                                    "myStruct": 
                                    {
                                        "myArray": 
                                        [
                                            None
                                        ]
                                    }
                                }
                            }
                        }
        
        
        for value in self.test_different_data_types:
            actual_output = self.driver._parse_flat_plc_var_to_dict({}, "Program.myStruct.myStruct.myArray[0]", value)
            correct_output["Program"]["myStruct"]["myStruct"]["myArray"][0] = value
            self.assertEqual(actual_output, 
                            correct_output, 
                            msg=self.test_output_string.format(correct=correct_output, actual=actual_output))
            self.assertEqual(len(correct_output["Program"]["myStruct"]["myStruct"]["myArray"]), 1, 
                             msg="Array length changed from 0 to" + 
                             str(len(correct_output["Program"]["myStruct"]["myStruct"]["myArray"])))


class TestParseNameComplex(omni.kit.test.AsyncTestCase):
    """Tests for complex variable parsing."""

    # Run before every test
    async def setUp(self):
        self.name_dict = {}
        self.driver = AdsDriver('127.0.0.1.1')
        self.test_output_string = "correct: {correct}\nactual: {actual}\n\n"

    def test_deep_mix_of_nesting(self):
        value = 30
        actual_output = self.driver._parse_flat_plc_var_to_dict({}, "Program.myStruct.myArray[1].myStruct.arr[3].myVar", value)
        correct_output =  {   "Program": {
                            "myStruct": 
                            {
                                "myArray": 
                                [
                                    None,
                                    {
                                        "myStruct": {
                                            "arr": [None, None, None, {"myVar" : value}]
                                            }
                                    }
                                ]
                            }
                        }
                    }
        self.assertEqual(actual_output, 
                         correct_output, 
                         msg=self.test_output_string.format(correct=correct_output, actual=actual_output))
