from typing import List
import os
import glob
import pandas as pd
import numpy as np
import sys

import json
from copy import deepcopy

import warnings
warnings.simplefilter(action='ignore', category=FutureWarning)

current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0,os.path.join(current_dir,"../"))
from data_structure.run_info import RunInfo
import data_processing.event_processor_all_channel as event_processor
import common.config_reader as common_config_reader
import common.metadata_handler as metadata_handler
from common.logger import setup_logger

logger = setup_logger(os.path.splitext(os.path.basename(__file__))[0])

# class MyTable(tables.IsDescription):
#     bin_full_path = tables.StringCol(itemsize=200) 
#     md_full_path = tables.StringCol(itemsize=200) 

class RunProcessor:
    ""
    def __init__(self):
        
        self.failure_flag = False
        
        self.common_cfg_reader = common_config_reader.ConfigurationReader()

        # set the paths
        self.path_config = self.common_cfg_reader.get_absolute_path_config()
        self.data_folders = self.path_config.get('RUN_ANALYSIS', 'data_dirs').split(' ')
        self.exclude_folders = self.path_config.get('RUN_ANALYSIS', 'exclude_dirs').split(' ')
        self.output_file = self.path_config.get('RUN_ANALYSIS', 'run_list_output_file')

        self.config = self.common_cfg_reader.get_data_processing_config()
        
        # settings for the run processor
        self.reprocess = self.config.getboolean('RUN_PROCESSOR_SETTINGS', 'reprocess')
        
        # settings for the gain processor
        self.hist_n_bins = int(self.config.get('GAIN_PROCESSOR_SETTINGS', 'hist_n_bins'))
        tmp = self.config.get("GAIN_PROCESSOR_SETTINGS", "hist_range")
        tmp = tmp.split(' ')
        self.hist_range = (float(tmp[0]),float(tmp[1]))
        
        self.hdf5_key = self.config.get('RUN_PROCESSOR_SETTINGS', 'hdf5_key')
        # self.hdf5_size_dict = {"bin_full_path":350, 
        #                         "md_full_path":350,
        #                         "run_tag":100,
        #                         "comment":350,
        #                         "area_hist_count_Vns":900,
        #                         "board_0_channels":100,
        #                         "board_1_channels":100,
        #                         "data_taking_mode":20}
        tmp = "HDF5_SIZE_SETTINGS"
        self.hdf5_size_dict = {
            key: self.config.getint(tmp, key)
            for key, _ in self.config.items(tmp)
        }

        # check self.hdf5_size_dict
        self.info = RunInfo()
        
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
                
        max_length = self.hdf5_size_dict["bin_full_path"]
        for i in data_files:
            if len(i)>max_length:
                max_length = len(i)
        
        if self.hdf5_size_dict["bin_full_path"] != max_length:
            logger.info("Need to reprocess all files as the path lengths are too long.")
            self.reprocess = True
                    
        return data_files

    def check_which_to_process(self, data_files: List[str], 
                               reprocess: bool = False) -> list:
        
        """
        check which files to process.
        If reprocess = True, the already processed files will be processed again.
        If the number of entries in the class RunInfo in src/common/run_info.py is not the same -> reprocess
        If reprocess = False and the output file already exists and no. of columns in the existing DataFrame 
        is the same as in the RunInfo class, then:
            - filter out the files that are already processed
            - return the list of files to process
        """
        
        existing_df = None
        if os.path.exists(self.output_file):
            hdf = pd.HDFStore(self.output_file, mode="r+")
            if self.hdf5_key in hdf:
                existing_df = pd.read_hdf(self.output_file, key=self.hdf5_key, mode="r+")
                logger.info(f"Run info for {len(existing_df)} runs found in {self.output_file}")
            else:
                reprocess = True
                logger.info(f"Cannot find the hdf5_key in the file. Need a new data file.")
            hdf.close()
        n_columns = len(self.info.__dict__)

        # Check if the existing DataFrame has the same number of columns as the new data
        length_existing_df = 0 if existing_df is None else len(existing_df.columns)
        logger.info("Number of columns match? " + str(length_existing_df == n_columns))
        logger.info("Are we reprocessing? " + str(reprocess))
        logger.info("existing_df is None? " + str(existing_df is None))
        
        # Convert the data_files list to a numpy array for faster processing
        data_files = np.array(data_files)

        # If not reprocessing, filter out the files that are already in the existing DataFrame
        if (not reprocess) and (existing_df is not None) and (length_existing_df == n_columns): 
            path_array = np.array(existing_df["md_full_path"].unique())
            
            # this step take a while
            logger.info(f"Determining which files are not processed yet...")
            data_files = data_files[~np.in1d(data_files, path_array)] # Filter out the files that are already processed
            
            logger.info(f"Processing {len(data_files)} new files")
            
            # self.hdf_read_mode = "a"
            
        elif (len(data_files) != 0): # and if need to reprocess
            logger.info(f"Processing {len(data_files)} new files")
            
            hdf = pd.HDFStore(self.output_file, mode='w')
            hdf.close()            
            
        else:
            logger.info("No new files to process")
            return
        
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
        
        self.info.set_info_from_dict(self.metadata.__dict__)
        self.bin_full_path_list = self.metadata.bin_full_path_list
        if self.info.data_taking_mode == "all_channels":
            self.channel_threshold_dict = self.metadata.channel_threshold_dict

        # assert len(self.info.bin_full_path) == 2
        
        return
    
    def get_n_channel_for_board(self, processing_mode: str, board_number: int, board_0_channels: list, board_1_channels: list) -> int:
        if processing_mode == "single_channel":
            board_channels = 1
        elif processing_mode == "all_channels":
            if board_number == 0: 
                board_channels = len(board_0_channels) 
            else:  
                board_channels = len(board_1_channels) 

        return board_channels

    def process_all_bins(self, md_full_path: str, more_info: bool = False) -> List[dict]:

        # refresh the flag in loop
        self.failure_flag = False 
        
        channel_level_data_list = []
        extra_data_list = []

        for board_number, bin_full_path in enumerate(self.bin_full_path_list):

            self.bin_full_path = bin_full_path
            self.info.board = board_number
            self.info.bin_full_path = bin_full_path

            # get number of channel on the board
            self.info.n_channels = self.get_n_channel_for_board(
                self.info.data_taking_mode,
                board_number, 
                self.info.board_0_channels, 
                self.info.board_1_channels)
            
            self.EventProcessor = event_processor.EventProcessor(self.info)
        
            for rel_channel in range(self.info.n_channels):

                self.EventProcessor.process_all_events(rel_channel)

                if self.EventProcessor.failure_flag == True:
                    logger.error(f"Processing of {md_full_path} failed for channel {rel_channel} on board {board_number}. Skipping this channel.")
                    self.failure_flag = True
                    continue

                self.EventProcessor.info.channel = self.info.board_0_channels[rel_channel] if board_number == 0 else self.info.board_1_channels[rel_channel]
                channel = str(self.EventProcessor.info.channel)
                self.EventProcessor.info.threshold_adc = self.channel_threshold_dict[channel]

                # data = self.EventProcessor.info.__dict__

                if more_info:
                    waveform = self.EventProcessor.get_randomly_selected_WF(rel_channel, 100)
                    areas_Vns = self.EventProcessor.areas_Vns
                    heights_V = self.EventProcessor.heights_V
                    extra_data = {"waveform": waveform,
                            "areas_Vns": areas_Vns,
                            "heights_V": heights_V}
                    
                    tmp = deepcopy(extra_data)
                    extra_data_list.append(tmp)
                    
                else:
                    extra_data = None

                tmp = deepcopy(self.EventProcessor.info)
                channel_level_data_list.append(tmp)

                # all processing
                # self.update_info_processed_events(rel_channel, set_waveform = False)

                # get actual channel number

        return (channel_level_data_list, extra_data_list)
    
    def process_runs(self):
        
        data = None
        
        # Check if "self.data_folders" is an aboslute path for a directory
        for data_folder in self.data_folders:
            if not os.path.isabs(data_folder) and not os.path.isdir(data_folder):
                raise ValueError(f"{data_folder} is not an absolute path for a directory")

        # Get the list of data files from self.data_folders
        # all metadata files in the data folders
        data_files = self.get_data_files(self.data_folders, self.exclude_folders)
        logger.info(f"Found {len(data_files)} metadata files in {self.data_folders}")

        # Generate the updated run_info DataFrame; write into self.output_file
        data_files = self.check_which_to_process(data_files, reprocess=self.reprocess)        
        
        # Just to check if the data_files are being processed correctly
        for md_full_path in data_files:
            
            # refresh the flag in loop
            self.failure_flag = False 
            
            # read the metadata file
            self.update_info_from_metafile(md_full_path)

            # make sure that it's all channels data file
            # if (self.failure_flag == True) or (self.info.data_taking_mode != "all_channels") or (len(self.bin_full_path_list) != 2):
            if (self.failure_flag == True):
                logger.error(f"Metadata file {md_full_path} is not valid or processing failed. Skipping this file.")
                continue

            # process all binary for the metadata file
            result = self.process_all_bins(md_full_path, more_info=False)

            for channel_level_data in result[0]:

                data = channel_level_data.__dict__

                # Create a DataFrame from the new data -> hdf; write to file in append mode
                if isinstance(data,dict):
                    new_df = pd.DataFrame.from_dict([data])
                    # new_df.to_hdf(self.output_file, key=self.hdf5_key, mode='a', 
                    #               append=True, format='table')
                    
                    precision = 5
                    new_df['area_hist_count_Vns'] = new_df['area_hist_count_Vns'].apply(lambda x: json.dumps(np.around(x, precision).tolist()))
                    new_df['area_bin_edges_Vns'] = new_df['area_bin_edges_Vns'].apply(lambda x: json.dumps(np.around(x, precision).tolist()))
                    new_df['channel_list'] = new_df['channel_list'].apply(json.dumps)
                    new_df['board_0_channels'] = new_df['board_0_channels'].apply(json.dumps)
                    new_df['board_1_channels'] = new_df['board_1_channels'].apply(json.dumps)
                    
                    hdf = pd.HDFStore(self.output_file, mode='a')
                    
                    hdf.append(self.hdf5_key, new_df, 
                                data_columns=new_df.columns,
                                index=False,
                                min_itemsize=self.hdf5_size_dict)
                    hdf.close()

            # else: 
                # raise ValueError(f"Data file {data_file} is not a valid single channel data file or processing failed.")

        
        # Load the updated run_info DataFrame
        if os.path.exists(self.output_file):
            run_info_df = pd.read_hdf(self.output_file, 
                                      key=self.hdf5_key,
                                      mode='r')
            
            # Sort the DataFrame by date and assign run_id
            run_info_df.sort_values("date_time", inplace=True)
            run_info_df.reset_index(drop=True, inplace=True)
            run_info_df["run_id"] = run_info_df.index + int(1)

            # Save the updated run_info DataFrame to self.output_file
            run_info_df.to_hdf(self.output_file, 
                               key=self.hdf5_key,
                               mode='w', 
                               format='table',
                               min_itemsize=self.hdf5_size_dict,
                               data_columns=True)

            logger.info("Run info DataFrame updated and saved to" + str(self.output_file))
            
        else:
            raise FileNotFoundError(f"Run info file {self.output_file} not found")

if __name__ == "__main__":
    processor = RunProcessor()
    processor.process_runs()
    logger.info("Finished.")
