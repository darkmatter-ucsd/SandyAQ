'''
This is a class that contains and define all metadata 
information of a single bin file, including all relavant
paths, all configuration files, all settings

To initialize, only the full path of either .bin or .json
is needed
'''

import os
import re
import pandas as pd
import datetime
import json
import sys

current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0,os.path.join(current_dir,"../"))
from common.logger import setup_logger
from data_structure.run_info import RunInfo

# logger = setup_logger(__name__)
logger = setup_logger(os.path.splitext(os.path.basename(__file__))[0])

class MetadataHandler(RunInfo):
    
    """
    A class to handle metadata information of a single bin or JSON file.
    
    Parameters:
        md_full_path (str): The full path to the input file (json).
    
    Attributes:
        failure_flag (bool): Indicator of whether the file was successfully read.
        
    Methods:
        check_path(filepath): Validates the input file path and checks its existence.
        set_attr_file_name(full_path): Sets the attributes from the file name.
        get_metadata_from_json(file_path): Set the attributes from the metadata (JSON) file.
        
    
    """
    
    def __init__(self, md_full_path: str):
        
        super().__init__()
        
        # self.run_info = run_info.RunInfo()
        self.failure_flag = False
        
        self.md_full_path = self.check_path(md_full_path, extension=".json")
        self.md_base_name = os.path.basename(self.md_full_path)
        self.md_dir_path = os.path.dirname(self.md_full_path)

        self._update_attr_from_file_name()
        self._update_attr_from_json()
        self._get_paired_files()
        
    def check_path(self, full_path: str, extension = ".json") -> str:
        """
        Validates the input file path and checks its existence.

        Args:
            full_path (str): The full path to the input file.
            extension (str): The file extension to check for. Default is .json.

        Returns:
            str: The validated file path.

        Raises:
            ValueError: If the file path is not absolute.
            TypeError: If the file extension is not .bin or .json.
            FileNotFoundError: If the file does not exist.
        """
        if os.path.isabs(full_path) == False:
            raise ValueError("md_full_path must be an absolute path.")
        
        if not (full_path.endswith(extension)):
            raise TypeError(f"File must have a {extension} extension.")
        
        if not os.path.isfile(full_path):
            raise FileNotFoundError(f"File not found: {full_path}")
        
        # check if the file name has "meta_config" in it
        if (extension == ".json") and ("meta_config" not in full_path):
            raise ValueError(f"File name must have 'meta_config' in it for json files.")
        if (extension == ".bin") and ("config" not in full_path):
            raise ValueError(f"File name must have 'config' in it for bin files.")
        
        return full_path
    
    def _update_attr_from_file_name(self) -> None:
        """
        Set attributes from the file name.
        
        This method is used when the metadata file does not contain
        the channel information, and it is extracted from the file name.
        
        Returns:
            None
            
        Raises:
            ValueError: If the file name does not match the expected pattern.
        """
        match = re.match(r"meta_config_(\d+)_(\d+)_(\d{8})_(\d{6})\.json", self.md_base_name)
        
        if match:
            self.data_taking_mode = "single_channel"

            channel, threshold_adc, date_str, time_str = match.groups()
            self.channel = int(channel)
            self.threshold_adc = int(threshold_adc)
            self.date_time_str = f"{date_str}_{time_str}"
        else:
            match = re.match(r"meta_config_all_(\d{8})_(\d{6})\.json", self.md_base_name)

            if match:
                self.data_taking_mode = "all_channels"
                date_str, time_str = match.groups()
                self.date_time_str = f"{date_str}_{time_str}"

            else:
                self.failure_flag = True
                raise ValueError("The file format does not match the expected pattern. \n" + \
                                "It should be in 'meta_config_{{channel}}_{{threshold}}" + \
                                "_{{date_YYYYMMDD}}_{{time_HHMMSS}}.json' for single channel data, or " + \
                                "'meta_config_all_{{date_YYYYMMDD}}_{{time_HHMMSS}}.json' for all channels data.")
    
    def _update_attr_from_json(self) -> None:
        """    
        Read from metadata file (json file); update the 
        attributes to this class; check parameters
        
        Returns:
            None
            
        Raises:
            raise TypeError: If "run_tag" in the json file is neither 
                              str or list.
        """
        # just to be sure
        if self.failure_flag == True:
            return None
        
        logger.info(f"Reading from: {self.md_full_path}")
        with open(self.md_full_path, "r") as file:
            meta_data = json.load(file)
            
        # overwrite the datetime if start_timestamp exist
        _tmp = meta_data.get("start_timestamp")
        if _tmp != None:
            self.date_time = pd.to_datetime(_tmp, format="%Y-%m-%d %H:%M:%S.%f")
        else:
            raise ValueError("Start timestamp is missing in the metadata file.")
        
        _tmp = meta_data.get("comment")
        if _tmp != None:
            self.comment = str(_tmp)
        else:
            # raise ValueError("Comment is missing in the metadata file.")
            self.comment = "No comment provided."
        
        # Parse the time string into a timedelta object
        _tmp = meta_data.get("runtime")
        if _tmp != None:
            time_obj = datetime.datetime.strptime(_tmp, "%H:%M:%S.%f")
            # Calculate total seconds
            self.runtime_s = time_obj.hour * 3600 + time_obj.minute * 60 + time_obj.second + time_obj.microsecond / 1e6
        # else:
            # self.failure_flag = True
            # raise ValueError("Runtime is missing in the metadata file.")

        voltage_config = meta_data.get("voltage_config")
        if voltage_config:
            self.voltage_preamp1_V = float(voltage_config["preamp_1"])  # Assume all preamps have the same voltage
        else:
            raise ValueError("Voltage configuration is missing in the metadata file.")
            
        self.temperature_K = meta_data.get("temperature")
        if self.temperature_K < 0:
            self.temperature_K = self.temperature_K + 273 # convert to Kelvin
        else:
            raise ValueError("Temperature is missing in the metadata file.")
        
        _tmp = meta_data.get("board_0_channels")
        if _tmp != None:
            self.board_0_channels = list(_tmp)
        else:
            raise ValueError("Board 0 channels are missing in the metadata file.")

        _tmp = meta_data.get("board_1_channels")
        if _tmp != None:
            self.board_1_channels = list(_tmp)
        else:
            raise ValueError("Board 1 channels are missing in the metadata file.")
        
        #### run tag: whether run_tag is str or list in meta_data file -> into list of run tags
        _tmp = meta_data.get("run_tag")
        _tmp__list = []
        if _tmp != None:
            _run__tag = _tmp
            if type(_run__tag) == list:
                for i in _run__tag:
                    _tmp__list.append(i)
            elif type(_run__tag) == str:
                _tmp__list.append(_run__tag)
            else:
                raise TypeError
        elif (os.path.dirname(self.bin_full_path).find("/threshold_calibration") != -1): # find returns -1 if not found
            _tmp__list.append("threshold_calibration")
        else:
            _tmp__list.append("GXe/gain_calibration") # started out with GXe calibration and didn't have run_tag in the meta file

        # FIXME: hard-code tag
        _split_file_path = self.bin_full_path.split("/")
        _split_file_path = "/".join(_split_file_path[3:]) # remove /home/daqtest/ or path for home for (**)
        
        if "trash" in self.bin_full_path: 
            _tmp__list.append("trash")
            
        if "test" in _split_file_path: # ref(**)
            _tmp__list.append("test")
            
        self.run_tag = "|".join(_tmp__list)

        if (meta_data.get("run_tag") == None):
            logger.warning("PLEASE update metda data file, run_tag is missing")
            raise ValueError("Run tag is missing in the metadata file.")
        
        #### data taking mode
        if self.data_taking_mode == None:
            _tmp = meta_data.get("data_taking_mode")
            if _tmp != None:
                self.data_taking_mode = str(_tmp)
            else:
                self.failure_flag = True
                raise ValueError("Data taking mode is not known either from the file name or in the metadata file.")

        if self.data_taking_mode == "single_channel":
            self.n_channels = 1

            _tmp = meta_data.get("channel")
            if _tmp != None:
                assert int(_tmp) == self.channel
            
            _tmp = meta_data.get("board")
            if _tmp != None:
                self.board = int(_tmp)
            elif self.channel in self.board_0_channels:
                self.board = 0
            elif self.channel in self.board_1_channels:
                self.board = 1
            else:
                self.failure_flag = True
                raise ValueError("Board number is undetermined")
            

            _tmp = meta_data.get("threshold")
            if _tmp != None:
                assert int(self.threshold_adc) == self.threshold_adc

            _tmp = meta_data.get("channel_list")
            if _tmp != None:
                self.channel_list = _tmp
            else:
                self.channel_list = list(range(0, 24))
                
        elif self.data_taking_mode == "all_channels":

            _tmp = meta_data.get("channel_list")
            if _tmp != None:
                self.channel_list = _tmp
                # self.n_channels = len(_tmp)
            else:
                self.failure_flag = True
                raise ValueError("Channel list is missing in the metadata file for all channels data.")

            _tmp = meta_data.get("channel_threshold_dict")
            if _tmp != None:
                self.channel_threshold_dict = _tmp


        _tmp = meta_data.get("number_of_events")
        if _tmp != None:
            self.number_of_events = int(meta_data.get("number_of_events")) # FIXME: number_of_events is not saved as integer
        else:
            raise ValueError("Number of events is missing in the metadata file.")

        _tmp = meta_data.get("post_trigger")
        if _tmp != None:
            self.post_trigger = float(_tmp)

        _tmp = meta_data.get("DC_OFFSET")
        if _tmp != None:
            self.DC_OFFSET = float(_tmp)

        _tmp = meta_data.get("record_length")
        if _tmp != None:
            self.record_length_sample = int(_tmp)
        else:
            self.failure_flag = True
            raise ValueError("Record length is missing in the metadata file.")
        
        return None
    
    def _get_paired_files(self) -> None:
        """    
        Map the json file name (metadata full path) to binary file name.
        It also collect all information from the file name and 
        set them as attributes of this class.
        
        Returns:
            None
            
        Raises:
            raise ValueError: If the file name does not match the requirement.
        
        """
        
        ### if file path is a json file
        if self.data_taking_mode == "single_channel":
            
            self.bin_base_name = f"config_{self.channel}" + \
                                f"_{self.threshold_adc}" + \
                                f"_{self.date_time_str}" + \
                                f"_board_{self.board}.bin"
            self.bin_dir_path = self.md_dir_path
            self.bin_full_path = os.path.join(self.bin_dir_path, self.bin_base_name)
            self.bin_full_path_list = [self.bin_full_path]

            # self.check_path(self.bin_full_path, extension=".bin")
            
            if os.path.isfile(self.bin_full_path) == False:
                self.failure_flag = True
                logger.warning(f"Cannot find the corresponding binary file: {self.bin_full_path}.")
                
                # raise FileNotFoundError(f"Cannot find the corresponding binary file: {self.bin_full_path}.")
                
                
        elif self.data_taking_mode == "all_channels":
            
            self.bin_dir_path = self.md_dir_path
            board0_bin_base_name = f"config_all" + \
                                f"_{self.date_time_str}" + \
                                f"_board_0.bin"
            board0_bin_full_path = os.path.join(self.bin_dir_path, board0_bin_base_name)
            
            board1_bin_base_name = f"config_all" + \
                                f"_{self.date_time_str}" + \
                                f"_board_1.bin"
            board1_bin_full_path = os.path.join(self.bin_dir_path, board1_bin_base_name)
            
            if os.path.isfile(board0_bin_full_path) == False:
                self.failure_flag = True
                logger.warning(f"Cannot find the corresponding binary file for board 0: {board0_bin_full_path}.")
                
                # raise FileNotFoundError(f"Cannot find the corresponding binary file: {board0_bin_full_path}.")
            
            if os.path.isfile(board1_bin_full_path) == False:
                self.failure_flag = True
                logger.warning(f"Cannot find the corresponding binary file for board 0: {board1_bin_full_path}.")
                
                # raise FileNotFoundError(f"Cannot find the corresponding binary file: {board1_bin_full_path}.")
            
            self.bin_full_path_list = [board0_bin_full_path, board1_bin_full_path]
            self.bin_full_path = None
            self.bin_base_name = board0_bin_base_name
            
            
        return None


