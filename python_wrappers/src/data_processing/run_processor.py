from typing import List
import os
import glob
import pandas as pd
import json
import numpy as np
import sys

import datetime
import csv

import warnings
warnings.simplefilter(action='ignore', category=FutureWarning)

current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0,os.path.join(current_dir,"../"))
import data_processing.run_info as run_info
import data_processing.event_processor as event_processor
import common.config_reader as common_config_reader
import common.metadata_handler as metadata_handler
from common.logger import setup_logger

logger = setup_logger(os.path.splitext(os.path.basename(__file__))[0])

class RunProcessor:
    ""
    def __init__(self):
        
        self.failure_flag = True
        
        self.common_cfg_reader = common_config_reader.ConfigurationReader()
        self.config = self.common_cfg_reader.get_data_processing_config()
        
        self.data_folders = self.config.get('RUN_PROCESSOR_SETTINGS', 'data_folders').split(' ')
        self.exclude_folders = self.config.get('RUN_PROCESSOR_SETTINGS', 'exclude_folders').split(' ')
        self.output_file = self.config.get('RUN_PROCESSOR_SETTINGS', 'run_list_output')
        
        self.reprocess = self.config.getboolean('RUN_PROCESSOR_SETTINGS', 'reprocess')
        
        self.info = run_info.RunInfo()

    def get_data_files(self, data_directories: List[str], exclude_directories: List[str]) -> List[str]:
        """
        Get all the data files in the given data directories
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
        self.info.voltage_preamp1_V = self.metadata.voltage_preamp1_V
        self.info.temperature_K = self.metadata.temperature_K
        
        self.info.number_of_events = self.metadata.number_of_events
        
        self.info.record_length_sample = self.metadata.record_length_sample
        
        self.failure_flag = False
        
        return
    
    def update_info_processed_events(self, set_waveform = False):
        
        if self.failure_flag == False:
            self.EventProcessor = event_processor.EventProcessor(self.info.bin_full_path,
                                                    self.info.number_of_events,
                                                    self.info.record_length_sample)
            self.EventProcessor.process_all_events(set_waveform = set_waveform)
            
            if self.EventProcessor.failure_flag == False:
                self.info.baseline_n_samples = self.EventProcessor.baseline_n_samples
                self.info.baseline_n_samples_avg = self.EventProcessor.baseline_n_samples_avg
                self.info.n_channels = self.EventProcessor.n_channels
                
                self.info.baseline_std = self.EventProcessor.baseline_std
                self.info.baseline_mean = self.EventProcessor.baseline_mean
                self.info.n_processed_events = self.EventProcessor.n_processed_events
                self.info.start_index = self.EventProcessor.start_index
                
            else: 
                self.failure_flag = True
                
        return
               
    def single_data_file_to_dict(self, md_full_path: str, set_waveform = False):

        self.update_info_from_metafile(md_full_path)
        self.update_info_processed_events(set_waveform = set_waveform)
        
        if self.failure_flag == False:
            return self.info.__dict__
        else:
            return None
        
    def check_which_to_process(self, data_files: List[str], 
                               reprocess: bool = False) -> list:
        """
        Convert the list of data files into a dataframe
        - extract date, channel, threshold from the file name 
        - attach the information to the dataframe
        - sort the dataframe by date and assign run_id
        - find the corresponding meta file
        - read voltage, temperature from the meta file
        """
        
        if os.path.exists(self.output_file):
            existing_df = pd.read_csv(self.output_file, parse_dates=["date_time"],delimiter=",",quotechar='"', skipinitialspace=True, encoding="utf-8")
            logger.info(f"Run info for {len(existing_df)} runs found in {self.output_file}")
        else:
            existing_df = None

        n_columns = len(self.info.__dict__)

        # Check if the existing DataFrame has the same number of columns as the new data
        length_existing_df = 0 if existing_df is None else len(existing_df.columns)
        logger.info("Number of columns match? " + str(length_existing_df == n_columns))
        logger.info("Not reprocessing? " + str(not reprocess))
        logger.info("existing_df is not None? " + str(existing_df is not None))
        
        # Convert the data_files list to a numpy array for faster processing
        data_files = np.array(data_files)

        # If not reprocessing, filter out the files that are already in the existing DataFrame
        if (not reprocess) and (existing_df is not None) and (length_existing_df == n_columns): 
            path_array = np.array(existing_df["md_full_path"].unique())
            
            # this step take a while
            logger.info(f"Determining which files are not processed yet...")
            data_files = data_files[~np.in1d(data_files, path_array)] # Filter out the files that are already processed
            
            logger.info(f"Processing {len(data_files)} new files")
            
        elif (len(data_files) != 0):
            # write the header to csv file
            logger.info(f"Processing {len(data_files)} new files")
            data_df = pd.DataFrame(columns=self.info.__dict__.keys())
            data_df.iloc[:0].to_csv(self.output_file, index=False, quoting=csv.QUOTE_NONNUMERIC)
        else:
            logger.info("No new files to process")
            return
        
        return data_files
    
    def process_runs(self):
        
        data = None
        
        # Check if "self.data_folders" is an aboslute path for a directory
        for data_folder in self.data_folders:
            if not os.path.isabs(data_folder) and not os.path.isdir(data_folder):
                raise ValueError(f"{data_folder} is not an absolute path for a directory")

        # Get the list of data files from self.data_folders
        data_files = self.get_data_files(self.data_folders, self.exclude_folders)
        logger.info(f"Found {len(data_files)} metadata files in {self.data_folders}")

        # Generate the updated run_info DataFrame; write into self.output_file
        data_files = self.check_which_to_process(data_files, reprocess=self.reprocess)
        
        # Just to check if the data_files are being processed correctly
        for data_file in data_files:
            self.failure_flag = True # refresh the flag in loop
            
            data = self.single_data_file_to_dict(data_file) 

            # Create a DataFrame from the new data -> csv; write to file in append mode
            if isinstance(data,dict):
                new_df = pd.DataFrame.from_dict([data])
                new_df.to_csv(self.output_file, mode='a', index=False, 
                            header=False, quoting=csv.QUOTE_NONNUMERIC)

        # Load the updated run_info DataFrame
        if os.path.exists(self.output_file):
            # run_info_df = pd.read_csv(self.output_file)
            run_info_df = pd.read_csv(self.output_file, 
                                      parse_dates=["date_time"],
                                      delimiter=",",
                                      quotechar='"', 
                                      skipinitialspace=True, 
                                      encoding="utf-8")
            
            # Sort the DataFrame by date and assign run_id
            run_info_df.sort_values("date_time", inplace=True)
            run_info_df.reset_index(drop=True, inplace=True)
            run_info_df["run_id"] = run_info_df.index + 1

            # Save the updated run_info DataFrame to self.output_file
            run_info_df.to_csv(self.output_file, index=False, quoting=csv.QUOTE_NONNUMERIC)

            logger.info("Run info DataFrame updated and saved to" + str(self.output_file))
            
        else:
            raise FileNotFoundError(f"Run info file {self.output_file} not found")

if __name__ == "__main__":
    processor = RunProcessor()
    processor.process_runs()