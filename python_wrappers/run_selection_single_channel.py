from typing import List
import os
import glob
import pandas as pd
import json
import re
import numpy as np
import configparser
import sys
import datetime
import csv

from dataclasses import dataclass, field

import WaveformProcessor
sys.path.insert(0,"/home/daqtest/Processor/sandpro")
import sandpro

DATA_FOLDERS = [
    "/home/daqtest/DAQ/SandyAQ/softlink_to_data/all_data/",
    # Add more data folders as needed, need to be an absolute path
]

EXCLUDE_FOLDERS = [
    "/home/daqtest/DAQ/SandyAQ/softlink_to_data/all_data/20240701_T102_47V_6.5sig",
    "/home/daqtest/DAQ/SandyAQ/softlink_to_data/all_data/20240701_T102_47V_7.0sig",
    "/home/daqtest/DAQ/SandyAQ/softlink_to_data/all_data/20240701_T102_47V_7.5sig"
]

EXCLUDE_FOLDERS = []

RUN_INFO_FILE = "run_info_single_channel.csv" #output

REPROCESS = False

@dataclass
class RunInfo:
    '''
    Dataclass to store the run information
    Will rerun from beginning if the number of columns is changed
    '''
    file_path: str = ""
    date_time: pd.Timestamp = np.nan
    # run_tag: list = field(default_factory=list)
    run_tag: str = ""
    comment: str = ""
    
    number_of_channels: int = 1
    channel: int = np.nan
    board: int = np.nan
    threshold_adc: int = np.nan

    runtime_s: float = np.nan
    voltage_preamp1_V: float = np.nan
    temperature_K: float = np.nan
    
    number_of_events: int = np.nan
    n_processed_events: int = np.nan
    start_index: int = np.nan
    
    record_length_sample: int = np.nan
    baseline_n_samples: int = 120
    baseline_n_samples_avg: int = 40
    baseline_std: float = np.nan
    baseline_mean: float = np.nan
    


def get_data_files(data_directories: List[str], exclude_directories: List[str]) -> List[str]:
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
            data_files_name = glob.glob(os.path.join(root, "config_*.bin"))
            data_files.extend(data_files_name)
                
    return data_files

def single_data_file_to_dict(file_path: str) -> dict:

    info = RunInfo()
    info.file_path = file_path

    # Extract date, channel, threshold from the file name
    file_name = os.path.basename(info.file_path)
    match = re.match(r"config_(\d+)_(\d+)_(\d{8})_(\d{6})_board_(\d+)\.bin", file_name)

    # Extract the basic identifier information from the file name that matches the pattern
    if match:
        info.channel, info.threshold_adc, date, time, info.board = match.groups()
        info.channel = int(info.channel)
        info.threshold_adc = int(info.threshold_adc)
        info.board = int(info.board)
        file_dir = os.path.dirname(info.file_path)
        
        # Check if the run is valid based on the channel and board combination
        if (0 <= info.channel <= 15 and info.board == 0) or (info.channel > 15 and info.board == 1): # FIXME: can move out of the loop
            info.date_time = pd.to_datetime(f"{date}_{time}", format="%Y%m%d_%H%M%S")
            
            # Find the corresponding meta file
            meta_file = os.path.join(file_dir, f"meta_config_{info.channel}_{info.threshold_adc}_{date}_{time}.json")
            config_file = os.path.join(file_dir, "tmp", f"config_{info.channel}_{info.threshold_adc}.ini")
            
            # Read voltage and temperature from the meta file
            if os.path.exists(meta_file):
                #print(f"Reading meta file: {meta_file}")

                with open(meta_file, "r") as file:
                    meta_data = json.load(file)
                    
                voltage_config = meta_data.get("voltage_config")
                if voltage_config:
                    # info.voltage_preamp1 = list(voltage_config.values())[0]  # Assume all preamps have the same voltage
                    info.voltage_preamp1_V = voltage_config["preamp_1"]  # Assume all preamps have the same voltage
                    
                info.temperature_K = meta_data.get("temperature")
                if info.temperature_K < 0:
                    info.temperature_K = info.temperature_K + 273 # convert to Kelvin
                
                # Parse the time string into a timedelta object
                _tmp = meta_data.get("runtime")
                if _tmp != None:
                    time_obj = datetime.datetime.strptime(meta_data.get("runtime"), "%H:%M:%S.%f")
                    # Calculate total seconds
                    info.runtime_s = time_obj.hour * 3600 + time_obj.minute * 60 + time_obj.second + time_obj.microsecond / 1e6

                _tmp = meta_data.get("comment")
                if _tmp != None:
                    info.comment = str(_tmp)
                
                _tmp = meta_data.get("number_of_events")
                if _tmp != None:
                    info.number_of_events = int(meta_data.get("number_of_events")) # FIXME: number_of_events is not saved as integer
                # info.number_of_events = int(info.number_of_events) # FIXME: number_of_events is not saved as integer
                
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
                elif (os.path.dirname(info.file_path).find("/threshold_calibration") != -1):
                    _tmp__list.append("threshold_calibration")
                else:
                    _tmp__list.append("GXe/gain_calibration") # started out with GXe calibration and didn't have run_tag in the meta file

                # FIXME: hard-code tag
                _split_file_path = info.file_path.split("/")
                _split_file_path = "/".join(_split_file_path[3:]) # remove /home/daqtest/ or path for home for (**)
                
                if "trash" in info.file_path: 
                    _tmp__list.append("trash")
                    
                if "test" in _split_file_path: # ref(**)
                    _tmp__list.append("test")
                    
                info.run_tag = "|".join(_tmp__list)

                if (meta_data.get("run_tag") == None):
                    new_meta_data = meta_data.copy()
                    new_meta_data["run_tag"] = info.run_tag

                    _base_name = os.path.basename(meta_file)
                    _path_name = os.path.dirname(meta_file)
                    new_file_name = os.path.join(_path_name, f"new_{_base_name}")

                    print(f"Writing new meta file: {new_file_name}")
                    with open(new_file_name, "w") as file:
                        json.dump(new_meta_data, file, indent=4)
                        
                    print("PLEASE update metda data file, run_tag is missing")

            truncate_event_front = 1000 #index to truncate the events before
            truncate_event_back = 500 #index to truncate the events after

            if os.path.exists(config_file) and (info.number_of_events > (truncate_event_front + truncate_event_back)):
                    
                    start_index, end_index = truncate_event_front, info.number_of_events - truncate_event_back -1 #first 1000 events are noisy # the last 500 events might be empty

                    config = configparser.ConfigParser()
                    config.optionxform = str
                    config.read(config_file)

                    info.record_length_sample = int(config.get("COMMON", "RECORD_LENGTH"))

                    process_config = {"nchs": info.number_of_channels,
                    "nsamps": info.record_length_sample,
                    "sample_selection": info.baseline_n_samples, 
                    "samples_to_average": info.baseline_n_samples_avg}

                    # dump the config to a json file
                    with open("process_config.json", "w") as f:
                        json.dump(process_config, f, indent=4)

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
                        info.n_processed_events = int(len(wfp.baseline_rms))
                        info.start_index = int(start_index)

                    except Exception as e:
                        print(e)
                        try:
                            waveform = processor.get_rawdata_numpy(1999,
                                                        file=info.file_path, # specific .bin file
                                                        bit_of_daq=14,
                                                        headersize=4,inversion=False)
                            start_index, end_index = 1000, 1900 #first 1000 events are noisy

                            wfp = WaveformProcessor.WFProcessor(file_dir, volt_per_adc=2/2**14)
                            wfp.set_data(waveform["data_per_channel"][start_index:end_index,0], in_adc = False)
                            wfp.process_wfs()
                            
                            info.baseline_std = np.mean(wfp.baseline_rms)
                            info.baseline_mean = np.mean(wfp.baseline)
                            info.n_processed_events = int(len(wfp.baseline_rms))
                            
                        except Exception as e:
                            print(e)
                            print("Error in reading the waveform for file: ", info.file_path)
            
            return info.__dict__
        return None
    return None

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

    # data = []
    data = None
    info = RunInfo()
    n_columns = len(info.__dict__)

    # Saving the data in chunks to avoid memory issues
    # chunk_size = 100

    # Check if the existing DataFrame has the same number of columns as the new data
    length_existing_df = 0 if existing_df is None else len(existing_df.columns)
    print("Number of columns match? ", (length_existing_df == n_columns+1))
    print("Not reprocessing? ", (not reprocess))
    print("existing_df is not None? ", (existing_df is not None))
    
    # Convert the data_files list to a numpy array for faster processing
    data_files = np.array(data_files)

    # If not reprocessing, filter out the files that are already in the existing DataFrame
    if (not reprocess) and (existing_df is not None) and (length_existing_df == n_columns+1): 
        path_array = np.array(existing_df["file_path"].unique())
        data_files = data_files[~np.in1d(data_files, path_array)] # Filter out the files that are already processed
        print(f"Processing {len(data_files)} new files")
        
    elif (len(data_files) != 0):
        # write the header to csv file
        print(f"Processing {len(data_files)} new files")
        data_df = pd.DataFrame(columns=info.__dict__.keys())
        data_df.iloc[:0].to_csv(RUN_INFO_FILE, index=False, quoting=csv.QUOTE_MINIMAL)
    else:
        print("No new files to process")
        return
    
    # Just to check if the data_files are being processed correctly
    for data_file in data_files:

        try:
            data = single_data_file_to_dict(data_file) 
            # data = data[data != np.array(None)] # Remove any None values
        except Exception as e:
            print(f"Error processing data: {e}")
            continue

        # Create a DataFrame from the new data -> csv; write to file in append mode
        if data != None:
            new_df = pd.DataFrame.from_dict([data])
            new_df.to_csv(RUN_INFO_FILE, mode='a', index=False, 
                          header=False, quoting=csv.QUOTE_NONNUMERIC)

    # Main loop to process the data in chunks
    # for i in range(0, len(data_files), chunk_size):
    #     # Process the chunk of data (e.g., perform calculations, transformations, etc.)
    #     processed_chunk = data_files[i:i+chunk_size]

    #     try:
    #         data = v_single_data_file_to_dict(processed_chunk) # Convert the chunk of data
    #         data = data[data != np.array(None)] # Remove any None values
    #     except Exception as e:
    #         print(f"Error processing data: {e}")
    #         # print(data_files[i:i+chunk_size])
    #         continue

    #     # Create a DataFrame from the new data -> csv
    #     new_df = pd.DataFrame(data.tolist())
    #     new_df.to_csv(RUN_INFO_FILE, mode='a', index=False, header=False)
    
    return

def main():
    # Load the existing run_info DataFrame if it exists
    if os.path.exists(RUN_INFO_FILE):
        run_info_df = pd.read_csv(RUN_INFO_FILE, parse_dates=["date_time"],delimiter=",",quotechar='"', skipinitialspace=True, encoding="utf-8")
        print(f"Run info for {len(run_info_df)} runs found in {RUN_INFO_FILE}")
    else:
        run_info_df = None

    # Check if "DATA_FOLDERS" is an aboslute path for a directory
    for data_folder in DATA_FOLDERS:
        if not os.path.isabs(data_folder) and not os.path.isdir(data_folder):
            raise ValueError(f"{data_folder} is not an absolute path for a directory")

    # Get the list of data files from DATA_FOLDERS
    data_files = get_data_files(DATA_FOLDERS, EXCLUDE_FOLDERS)
    print(f"Found {len(data_files)} data files in {DATA_FOLDERS}")

    # Generate the updated run_info DataFrame; write into RUN_INFO_FILE
    data_files_to_csv(data_files, existing_df=run_info_df, reprocess=REPROCESS)

    # Save the updated run_info DataFrame to RUN_INFO_FILE
    # updated_run_info_df.to_csv(RUN_INFO_FILE, index=False)

    # Load the updated run_info DataFrame
    if os.path.exists(RUN_INFO_FILE):
        # run_info_df = pd.read_csv(RUN_INFO_FILE)
        run_info_df = pd.read_csv(RUN_INFO_FILE, parse_dates=["date_time"],delimiter=",",quotechar='"', skipinitialspace=True, encoding="utf-8")
        
    else:
        raise FileNotFoundError(f"Run info file {RUN_INFO_FILE} not found")

    # Sort the DataFrame by date and assign run_id
    run_info_df.sort_values("date_time", inplace=True)
    run_info_df.reset_index(drop=True, inplace=True)
    run_info_df["run_id"] = run_info_df.index + 1

    # Save the updated run_info DataFrame to RUN_INFO_FILE
    run_info_df.to_csv(RUN_INFO_FILE, index=False, quoting=csv.QUOTE_NONNUMERIC)

    print("Run info DataFrame updated and saved to", RUN_INFO_FILE)

if __name__ == "__main__":
    main()