from typing import List
import os
import glob
import pandas as pd
import json
import re
import numpy as np
import configparser
import sys

from dataclasses import dataclass

import WaveformProcessor
sys.path.insert(0,"/home/daqtest/Processor/sandpro")
import sandpro

DATA_FOLDERS = [
    "/home/daqtest/DAQ/SandyAQ/softlink_to_data/",
    # Add more data folders as needed, need to be an absolute path
]

RUN_INFO_FILE = "run_info.csv" #output

# LIST_OF_VARIABLES = ['file_path', 'run_id', 'channel', 'threshold', 'date_time', 'board', 'voltage_preamp1', 'temperature', 'comment', 'number_of_events', 'calibration_tag', 'baseline_std', 'baseline_mean', 'n_processed_events']

REPROCESS = True


@dataclass
class RunInfo:
    file_path: str = ""
    channel: int = np.nan
    comment: str = ""
    threshold: int = np.nan
    date_time: pd.Timestamp = np.nan
    board: int = np.nan
    voltage_preamp1: float = np.nan
    temperature: float = np.nan
    number_of_events: int = np.nan
    calibration_tag: bool = np.nan
    baseline_std: float = np.nan
    baseline_mean: float = np.nan
    n_processed_events: int = np.nan


def get_data_files(data_directories: List[str]) -> List[str]:
    """
    Get all the data files in the given data directories
    Also search subdirectories
    """
    data_files = []
    for data_directory in data_directories:
        data_files.extend(glob.glob(os.path.join(data_directory, "**/config_*.bin"), recursive=True))
    return data_files

def single_data_file_to_dict(file_path: str) -> dict:

    info = RunInfo()
    info.file_path = file_path

    # Extract date, channel, threshold from the file name
    file_name = os.path.basename(info.file_path)
    match = re.match(r"config_(\d+)_(\d+)_(\d{8})_(\d{6})_board_(\d+)\.bin", file_name)

    if match:
        info.channel, info.threshold, date, time, info.board = match.groups()
        info.channel = int(info.channel)
        info.board = int(info.board)
        file_dir = os.path.dirname(info.file_path)
        
        # Check if the run is valid based on the channel and board combination
        if (0 <= info.channel <= 15 and info.board == 0) or (info.channel > 15 and info.board == 1): # FIXME: can move out of the loop
            info.date_time = pd.to_datetime(f"{date}_{time}", format="%Y%m%d_%H%M%S")
            
            # Find the corresponding meta file
            meta_file = os.path.join(file_dir, f"meta_config_{info.channel}_{info.threshold}_{date}_{time}.json")
            config_file = os.path.join(file_dir, "tmp", f"config_{info.channel}_{info.threshold}.ini")
            
            # Read voltage and temperature from the meta file
            if os.path.exists(meta_file):
                with open(meta_file, "r") as file:
                    meta_data = json.load(file)
                    
                    voltage_config = meta_data.get("voltage_config")
                    if voltage_config:
                        # info.voltage_preamp1 = list(voltage_config.values())[0]  # Assume all preamps have the same voltage
                        info.voltage_preamp1 = voltage_config["preamp_1"]  # Assume all preamps have the same voltage
                        
                    info.temperature = meta_data.get("temperature")
                    
                    try: # Not all files contain comment and number_of_events
                        info.comment = meta_data.get("comment")
                        info.number_of_events = meta_data.get("number_of_events")
                    except:
                        info.comment = ""
                        info.number_of_events = 4000 #just a guess

                    if (os.path.dirname(info.file_path).find("calibration") != -1) or (meta_data.get("tag") == "calibration"):
                        info.calibration_tag = 1
                    else:
                        info.calibration_tag = 0
            
            truncate_event_front = 1000 #index to truncate the events before
            truncate_event_back = 500 #index to truncate the events after

            if os.path.exists(config_file) and (info.number_of_events > (truncate_event_front + truncate_event_back)):
                    
                    start_index, end_index = truncate_event_front, info.number_of_events - truncate_event_back -1 #first 1000 events are noisy # the last 500 events might be empty

                    config = configparser.ConfigParser()
                    config.optionxform = str
                    config.read(config_file)

                    process_config = {"nchs": 1,
                    "nsamps": int(config.get("COMMON", "RECORD_LENGTH")),
                    "sample_selection": 120,
                    "samples_to_average": 40}

                    # dump the config to a json file
                    with open("process_config.json", "w") as f:
                        json.dump(process_config, f)

                    processor= sandpro.processing.rawdata.RawData(config_file = "process_config.json",
                                                            perchannel=False) # what does this perchannel mean?

                    try:
                        waveform = processor.get_rawdata_numpy(n_evts=info.number_of_events-1,
                                                    file=info.file_path, # specific .bin file
                                                    bit_of_daq=14,
                                                    headersize=4,inversion=False)
                        
                        wfp = WaveformProcessor.WFProcessor(file_dir, volt_per_adc=2/2**14)
                        wfp.set_data(waveform["data_per_channel"][start_index:end_index,0], in_adc = False)
                        wfp.process_wfs()
                        
                        info.baseline_std = np.mean(wfp.baseline_rms)
                        info.baseline_mean = np.mean(wfp.baseline)
                        info.n_processed_events = len(wfp.baseline_rms)

                    except Exception as e:
                        print(e)
                        pass
            
    return info.__dict__

# v_single_data_file_to_dict = np.vectorize(single_data_file_to_dict, signature="()->(n)")
v_single_data_file_to_dict = np.vectorize(single_data_file_to_dict)

def data_files_to_csv(data_files: List[str], existing_df: pd.DataFrame = None, reprocess: bool = False):
    """
    Convert the list of data files into a dataframe
    - extract date, channel, threshold from the file name 
    - attach the information to the dataframe
    - sort the dataframe by date and assign run_id
    - find the corresponding meta file
    - read voltage, temperature from the meta file
    """

    data = []
    info = RunInfo()
    n_columns = len(info.__dict__)

    chunk_size = 100

    length_existing_df = 0 if existing_df is None else len(existing_df)
    print("Number of columns", (length_existing_df == n_columns))
    
    # Convert the data_files list to a numpy array for faster processing
    data_files = np.array(data_files)

    # Filter out the files that are already in the existing DataFrame
    if (not reprocess) and (existing_df is not None) and (length_existing_df == n_columns): 
        path_array = np.array(existing_df["file_path"].unique())
        data_files = data_files[~np.in1d(data_files, path_array)]
    elif (len(data_files) != 0):
        print(f"Processing {len(data_files)} new files")
        data_df = pd.DataFrame(columns=info.__dict__.keys())
        data_df.iloc[:0].to_csv(RUN_INFO_FILE, index=False)
    else:
        print("No new files to process")
        return

    # for info.file_path in data_files:
    #     # Check if the data file is already in the existing DataFrame (this is very slow)
    #     # if (not reprocess) and (existing_df is not None) and (info.file_path in existing_df["file_path"].values) and (length_existing_df == n_columns):
    #     #     continue

    #     # Extract date, channel, threshold from the file name
    #     file_name = os.path.basename(info.file_path)
    #     match = re.match(r"config_(\d+)_(\d+)_(\d{8})_(\d{6})_board_(\d+)\.bin", file_name)
    #     if match:
    #         info.channel, info.threshold, date, time, info.board = match.groups()
    #         info.channel = int(info.channel)
    #         info.board = int(info.board)
    #         file_dir = os.path.dirname(info.file_path)
            
    #         # Check if the run is valid based on the channel and board combination
    #         if (0 <= info.channel <= 15 and info.board == 0) or (info.channel > 15 and info.board == 1):
    #             info.date_time = pd.to_datetime(f"{date}_{time}", format="%Y%m%d_%H%M%S")
                
    #             # Find the corresponding meta file
    #             meta_file = os.path.join(file_dir, f"meta_config_{info.channel}_{info.threshold}_{date}_{time}.json")
    #             config_file = os.path.join(file_dir, "tmp", f"config_{info.channel}_{info.threshold}.ini")
                
    #             # Read voltage and temperature from the meta file
    #             if os.path.exists(meta_file):
    #                 with open(meta_file, "r") as file:
    #                     meta_data = json.load(file)
                        
    #                     voltage_config = meta_data.get("voltage_config")
    #                     if voltage_config:
    #                         # info.voltage_preamp1 = list(voltage_config.values())[0]  # Assume all preamps have the same voltage
    #                         info.voltage_preamp1 = voltage_config["preamp_1"]  # Assume all preamps have the same voltage
                            
    #                     info.temperature = meta_data.get("temperature")
                        
    #                     try: # Not all files contain comment and number_of_events
    #                         info.comment = meta_data.get("comment")
    #                         info.number_of_events = meta_data.get("number_of_events")
    #                     except:
    #                         info.comment = ""
    #                         info.number_of_events = 4000 #just a guess

    #                     if (os.path.dirname(info.file_path).find("calibration") != -1) or (meta_data.get("tag") == "calibration"):
    #                         info.calibration_tag = 1
    #                     else:
    #                         info.calibration_tag = 0
                
    #             truncate_event_front = 1000 #index to truncate the events before
    #             truncate_event_back = 500 #index to truncate the events after

    #             if os.path.exists(config_file) and (info.number_of_events > (truncate_event_front + truncate_event_back)):
                        
    #                     start_index, end_index = truncate_event_front, info.number_of_events - truncate_event_back -1 #first 1000 events are noisy # the last 500 events might be empty

    #                     config = configparser.ConfigParser()
    #                     config.optionxform = str
    #                     config.read(config_file)

    #                     process_config = {"nchs": 1,
    #                     "nsamps": int(config.get("COMMON", "RECORD_LENGTH")),
    #                     "sample_selection": 120,
    #                     "samples_to_average": 40}

    #                     # dump the config to a json file
    #                     with open("process_config.json", "w") as f:
    #                         json.dump(process_config, f)

    #                     processor= sandpro.processing.rawdata.RawData(config_file = "process_config.json",
    #                                                             perchannel=False) # what does this perchannel mean?

    #                     try:
    #                         waveform = processor.get_rawdata_numpy(n_evts=info.number_of_events-1,
    #                                                     file=info.file_path, # specific .bin file
    #                                                     bit_of_daq=14,
    #                                                     headersize=4,inversion=False)
                            
    #                         wfp = WaveformProcessor.WFProcessor(file_dir, volt_per_adc=2/2**14)
    #                         wfp.set_data(waveform["data_per_channel"][start_index:end_index,0], in_adc = False)
    #                         wfp.process_wfs()
                            
    #                         info.baseline_std = np.mean(wfp.baseline_rms)
    #                         info.baseline_mean = np.mean(wfp.baseline)
    #                         info.n_processed_events = len(wfp.baseline_rms)

    #                     except Exception as e:
    #                         print(e)
    #                         pass
                
    #             data.append(info.__dict__)
    for i in range(0, len(data_files), chunk_size):
        # Process the chunk of data (e.g., perform calculations, transformations, etc.)
        processed_chunk = data_files[i:i+chunk_size]
        data = v_single_data_file_to_dict(processed_chunk)

        # Create a DataFrame from the new data
        new_df = pd.DataFrame(data.tolist())
        
        # if (not reprocess) and (existing_df is not None) and (length_existing_df == n_columns):
        #     # Concatenate the existing DataFrame with the new DataFrame
        #     df = pd.concat([existing_df, new_df], ignore_index=True)
        # else:
        #     df = new_df

        new_df.to_csv(RUN_INFO_FILE, mode='a', index=False, header=False)
    
    return

def main():
    # Load the existing run_info DataFrame if it exists
    if os.path.exists(RUN_INFO_FILE):
        run_info_df = pd.read_csv(RUN_INFO_FILE)
        print(f"Run info for {len(run_info_df)} runs found in {RUN_INFO_FILE}")
    else:
        run_info_df = None

    # Check if "DATA_FOLDERS" is an aboslute path for a directory
    for data_folder in DATA_FOLDERS:
        if not os.path.isabs(data_folder) and not os.path.isdir(data_folder):
            raise ValueError(f"{data_folder} is not an absolute path for a directory")

    # Get the list of data files from DATA_FOLDERS
    data_files = get_data_files(DATA_FOLDERS)
    print(f"Found {len(data_files)} data files in {DATA_FOLDERS}")



    # Generate the updated run_info DataFrame; write into RUN_INFO_FILE
    data_files_to_csv(data_files, existing_df=run_info_df, reprocess=REPROCESS)

    # Save the updated run_info DataFrame to RUN_INFO_FILE
    # updated_run_info_df.to_csv(RUN_INFO_FILE, index=False)

    # Load the updated run_info DataFrame
    if os.path.exists(RUN_INFO_FILE):
        run_info_df = pd.read_csv(RUN_INFO_FILE)
    else:
        raise FileNotFoundError(f"Run info file {RUN_INFO_FILE} not found")

    # Sort the DataFrame by date and assign run_id
    run_info_df.sort_values("date_time", inplace=True)
    run_info_df.reset_index(drop=True, inplace=True)
    run_info_df["run_id"] = run_info_df.index + 1

    # Save the updated run_info DataFrame to RUN_INFO_FILE
    run_info_df.to_csv(RUN_INFO_FILE, index=False)

    print("Run info DataFrame updated and saved to", RUN_INFO_FILE)

if __name__ == "__main__":
    main()