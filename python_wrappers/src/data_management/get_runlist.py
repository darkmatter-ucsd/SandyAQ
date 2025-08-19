from typing import List
import os
import glob
import pandas as pd
import numpy as np
import sys

import json

import warnings
warnings.simplefilter(action='ignore', category=FutureWarning)

current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0,os.path.join(current_dir,"../"))
import common.run_info as run_info
import common.config_reader as common_config_reader
import common.metadata_handler as metadata_handler
from common.logger import setup_logger

logger = setup_logger(os.path.splitext(os.path.basename(__file__))[0])

# class MyTable(tables.IsDescription):
#     bin_full_path = tables.StringCol(itemsize=200) 
#     md_full_path = tables.StringCol(itemsize=200) 

class GetRunlist:
    ""
    def __init__(self):
        
        self.failure_flag = True
        
        self.common_cfg_reader = common_config_reader.ConfigurationReader()
        self.config = self.common_cfg_reader.get_data_processing_config()
        
        self.data_folders = self.config.get('RUN_PROCESSOR_SETTINGS', 'data_folders').split(' ')
        self.exclude_folders = self.config.get('RUN_PROCESSOR_SETTINGS', 'exclude_folders').split(' ')
        
        self.info = run_info.RunInfo()
        
    def get_data_files(self, data_directories: List[str], exclude_directories: List[str]) -> List[str]:
        """
        Get all the metadata files in the given data directories
        Also search subdirectories
        """
        data_files = []

        for data_directory in data_directories:
            for root, dirs, files in os.walk(data_directory):
                # Skip excluded directories
                dirs[:] = [d for d in dirs if os.path.join(root, d) not in exclude_directories]
                # Find matching files
                data_files_name = glob.glob(os.path.join(root, "meta_config_*.json"))
                data_files.extend(data_files_name)
                
        return data_files

    def update_info_from_metafile(self, md_full_path: str) -> None:
        """
        Convert the list of data files into a dataframe
        - extract date, channel, threshold from the file name 
        - attach the information to the dataframe
        - sort the dataframe by date and assign run_id
        - find the corresponding meta file
        - read voltage, temperature from the meta file
        """
        self.metadata = metadata_handler.MetadataHandler(md_full_path)
        
        if self.metadata.failure_flag == True:
            self.failure_flag = True
            return None
        
        self.info.bin_full_path = self.metadata.bin_full_path
        self.info.md_full_path = self.metadata.md_full_path
        
        self.info.channel = int(self.metadata.channel)
        self.info.threshold_adc = int(self.metadata.threshold_adc)
        self.info.board = int(self.metadata.board)
        self.info.date_time = self.metadata.date_time
        
        self.info.run_tag = self.metadata.run_tag
        self.info.comment = self.metadata.comment
        
        self.info.channel = self.metadata.channel
        
        self.info.runtime_s = self.metadata.runtime_s
        self.info.voltage_preamp1_V = float(self.metadata.voltage_preamp1_V)
        self.info.temperature_K = self.metadata.temperature_K
        
        self.info.number_of_events = self.metadata.number_of_events
        
        self.info.record_length_sample = self.metadata.record_length_sample
        
        self.failure_flag = False
        
        return
    
    
    def get_runlist(self):
        
        data = None
        
        # Check if "self.data_folders" is an aboslute path for a directory
        for data_folder in self.data_folders:
            if not os.path.isabs(data_folder) and not os.path.isdir(data_folder):
                raise ValueError(f"{data_folder} is not an absolute path for a directory")

        # Get the list of data files from self.data_folders
        data_files = self.get_data_files(self.data_folders, self.exclude_folders)
        logger.info(f"Found {len(data_files)} metadata files in {self.data_folders}")
        
        for data_file in data_files:
            self.update_info_from_metafile(data_file)
            
            if self.info.run_tag == "LXe/Cs137":
                print(data_file)
            
        return

if __name__ == "__main__":
    processor = GetRunlist()
    processor.get_runlist()
    logger.info("Finished.")