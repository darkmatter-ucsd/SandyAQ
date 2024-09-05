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
import data_processing.run_info as run_info

# logger = setup_logger(__name__)
logger = setup_logger(os.path.splitext(os.path.basename(__file__))[0])

class MetadataHandler(run_info.RunInfo):
    
    """
    A class to handle metadata information of a single bin or JSON file.
    
    Attributes:
        input_path (str): The full path to the input file (bin or json).
        failure_flag (bool): Indicator of whether the file was successfully read.
        
    Methods:
        check_path(filepath): Validates the input file path and checks its existence.
        set_attr_file_name(full_path): Sets the attributes from the file name.
        get_metadata_from_json(file_path): Set the attributes from the metadata (JSON) file.
    """
    
    def __init__(self, filepath: str):
        
        super().__init__()
        
        # self.run_info = run_info.RunInfo()
        self.failure_flag = False
        
        self.input_path = self.check_path(filepath)
        self.update_attr_from_file_name(self.input_path)
        self.update_attr_from_json(self.md_full_path)
        
    def check_path(self, filepath: str) -> str:
        """
        Validates the input file path and checks its existence.

        Args:
            filepath (str): The full path to the input file.

        Returns:
            str: The validated file path.

        Raises:
            ValueError: If the file path is not absolute.
            TypeError: If the file extension is not .bin or .json.
            FileNotFoundError: If the file does not exist.
        """
        if os.path.isabs(filepath) == False:
            raise ValueError("Filepath must be an absolute path.")
        
        if not (filepath.endswith('.bin')) and not (filepath.endswith('.json')):
            raise TypeError("File must have a .bin or .json extension.")
        
        if not os.path.isfile(filepath):
            raise FileNotFoundError(f"File not found: {filepath}")
        
        
        logger.info(f"Reading from: {filepath}")
        return filepath
        
    def update_attr_from_file_name(self, full_path: str) -> None:
        """    
        Map the binary file name to json file name, vice versa.
        It also collect all information from the file name and 
        set them as attributes of this class.
        
        Args:
            full_path (str): full json/bin path

        Returns:
            None
            
        Raises:
            raise ValueError: If the file name does not match the requirement.
        
        """
        
        ### if file path is a json file
        if full_path.endswith('.json'):
            basename = os.path.basename(full_path)
            match = re.match(r"meta_config_(\d+)_(\d+)_(\d{8})_(\d{6})\.json", basename)

            # extract the basic identifier information from the file name that matches the pattern
            if match:
                self.md_full_path = full_path
                self.md_base_name = basename
                self.md_dir_path = os.path.dirname(full_path)
                
                self.channel, self.threshold_adc, self.date_str, self.time_str = match.groups()
                self.channel = int(self.channel)
                self.threshold_adc = int(self.threshold_adc)
                
                self.date_time = pd.to_datetime(f"{self.date_str}_{self.time_str}", format="%Y%m%d_%H%M%S")
                
                self.board = int(self.get_board_number(self.channel))
                
                self.bin_base_name = f"config_{self.channel}" + \
                                    f"_{self.threshold_adc}" + \
                                    f"_{self.date_str}" + \
                                    f"_{self.time_str}" + \
                                    f"_board_{self.board}.bin"
                self.bin_dir_path = self.md_dir_path
                self.bin_full_path = os.path.join(self.bin_dir_path, self.bin_base_name)
                
                if os.path.isfile(self.bin_full_path) == False:
                    logger.warning(f"Cannot find the corresponding binary file: {self.bin_full_path}.")
                    self.failure_flag = True
                
            else:
                self.failure_flag = True
                raise ValueError(f"The file format of {full_path} does not match. \n" + \
                                f"It should be in 'meta_config_{{channel}}_{{threshold}}" + \
                                f"_{{date_YYYYMMDD}}_{{time_HHMMSS}}.json'")
                 
        ### if file path is a bin file
        elif full_path.endswith('.bin'):
            basename = os.path.basename(full_path)
            match = re.match(r"config_(\d+)_(\d+)_(\d{8})_(\d{6})_board_(\d+)\.bin", basename)

            # extract the basic identifier information from the file name that matches the pattern
            if match:
                self.bin_full_path = full_path
                self.bin_base_name = basename
                self.bin_dir_path = os.path.dirname(full_path)
                
                self.channel, self.threshold_adc, self.date_str, self.time_str, self.board = match.groups()
                self.channel = int(self.channel)
                self.threshold_adc = int(self.threshold_adc)
                self.board = int(self.board)
                
                self.date_time = pd.to_datetime(f"{self.date_str}_{self.time_str}", format="%Y%m%d_%H%M%S")
                
                self.md_base_name = f"meta_config_{self.channel}" + \
                                    f"_{self.threshold_adc}" + \
                                    f"_{self.date_str}" + \
                                    f"_{self.time_str}.json"
                self.md_dir_path = self.bin_dir_path
                self.md_full_path = os.path.join(self.md_dir_path, self.md_base_name)
                
                if os.path.isfile(self.md_full_path) == False:
                    logger.warning(f"Cannot find the corresponding meta_data file: {self.md_full_path}. Returning None")
                    self.failure_flag = True
            
            else:
                self.failure_flag = True
                raise ValueError(f"The file format of {full_path} does not match. \n" + \
                                f"It should be in 'config_{{channel}}_{{threshold}}" + \
                                f"_{{date_YYYYMMDD}}_{{time_HHMMSS}}_board_{{board}}.bin'")
                
        return None
                   
    def get_board_number(self, channel: int) -> int:
        
        """    
        Return the board number given the channel number. 
        Important: this might not always be true
        
        Args:
            channel (int): channel number
            
        Returns:
            board_number (int): board number corresponding to the
                                channel number
        """
        if channel <= 15:
            board_number = 0
        else:
            board_number = 1
            
        return int(board_number)
        
    def update_attr_from_json(self, md_full_path: str) -> None:
        """    
        Read from metadata file (json file) and update the 
        attributes to this class
        
        Args:
            md_full_path (str): full path of the metadata file
            
        Returns:
            None
            
        Raises:
            raise TypeError: If "run_tag" in the json file is neither 
                              str or list.
        """
        # just to be sure
        if self.failure_flag == True:
            return None
        
        # just to be sure
        if os.path.isfile(md_full_path) == False:
            return None
        
        with open(md_full_path, "r") as file:
            meta_data = json.load(file)
            
        voltage_config = meta_data.get("voltage_config")
        if voltage_config:
            self.voltage_preamp1_V = voltage_config["preamp_1"]  # Assume all preamps have the same voltage
            
        self.temperature_K = meta_data.get("temperature")
        if self.temperature_K < 0:
            self.temperature_K = self.temperature_K + 273 # convert to Kelvin
            
        _tmp = meta_data.get("record_length")
        if _tmp != None:
            self.record_length_sample = int(_tmp)
                
        # Parse the time string into a timedelta object
        _tmp = meta_data.get("runtime")
        if _tmp != None:
            time_obj = datetime.datetime.strptime(_tmp, "%H:%M:%S.%f")
            # Calculate total seconds
            self.runtime_s = time_obj.hour * 3600 + time_obj.minute * 60 + time_obj.second + time_obj.microsecond / 1e6

        # overwrite the datetime if start_timestamp exist
        _tmp = meta_data.get("start_timestamp")
        if _tmp != None:
            self.date_time = pd.to_datetime(_tmp, format="%Y-%m-%d %H:%M:%S.%f")

        
        _tmp = meta_data.get("comment")
        if _tmp != None:
            self.comment = str(_tmp)
        
        _tmp = meta_data.get("number_of_events")
        if _tmp != None:
            self.number_of_events = int(meta_data.get("number_of_events")) # FIXME: number_of_events is not saved as integer
        
        # Run tag: whether run_tag is str or list in meta_data file -> into list of run tags
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
        
        return None

