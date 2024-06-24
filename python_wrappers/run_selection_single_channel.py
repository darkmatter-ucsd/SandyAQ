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

from dataclasses import dataclass

import WaveformProcessor
sys.path.insert(0,"/home/daqtest/Processor/sandpro")
import sandpro

DATA_FOLDERS = [
    "/home/daqtest/DAQ/SandyAQ/softlink_to_data/all_data/",
    # Add more data folders as needed, need to be an absolute path
]

RUN_INFO_FILE = "run_info_single_channel.csv" #output

REPROCESS = True

@dataclass
class RunInfo:
    '''
    Dataclass to store the run information
    Will rerun from beginning if the number of columns is changed
    '''
    file_path: str = ""
    date_time: pd.Timestamp = np.nan
    run_tag: str = np.nan
    comment: str = np.nan
    
    number_of_channels: int = 1
    channel: int = np.nan
    board: int = np.nan
    threshold: int = np.nan

    runtime: float = np.nan
    voltage_preamp1: float = np.nan
    temperature: float = np.nan
    
    number_of_events: int = np.nan
    n_processed_events: int = np.nan
    record_length: int = np.nan
    baseline_n_samples: int = 120
    baseline_n_samples_avg: int = 40
    baseline_std: float = np.nan
    baseline_mean: float = np.nan


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

    # Extract the basic identifier information from the file name that matches the pattern
    if match:
        info.channel, info.threshold, date, time, info.board = match.groups()
        info.channel = int(info.channel)
        info.threshold = int(info.threshold)
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
                #print(f"Reading meta file: {meta_file}")

                with open(meta_file, "r") as file:
                    meta_data = json.load(file)
                    
                voltage_config = meta_data.get("voltage_config")
                if voltage_config:
                    # info.voltage_preamp1 = list(voltage_config.values())[0]  # Assume all preamps have the same voltage
                    info.voltage_preamp1 = voltage_config["preamp_1"]  # Assume all preamps have the same voltage
                    
                info.temperature = meta_data.get("temperature")
                
                try: # Not all files contain comment, number_of_events, runtime
                    info.comment = str(meta_data.get("comment"))
                    info.number_of_events = int(meta_data.get("number_of_events"))

                    # Parse the time string into a timedelta object
                    time_obj = datetime.datetime.strptime(meta_data.get("runtime"), "%H:%M:%S.%f")
                    # Calculate total seconds
                    info.runtime = time_obj.hour * 3600 + time_obj.minute * 60 + time_obj.second + time_obj.microsecond / 1e6

                except:
                    # info.comment = ""
                    pass
                
                # Run tag
                if (os.path.dirname(info.file_path).find("/threshold_calibration") != -1) or (meta_data.get("run_tag") == "threshold_calibration"):
                    info.run_tag = "threshold_calibration"
                elif (meta_data.get("run_tag")!= None):
                    info.run_tag = meta_data.get("run_tag")
                else:
                    info.run_tag = "GXe/gain_calibration" # started out with GXe calibration and didn't have run_tag in the meta file

                # # remove after running once; add tag in previous runs
                # new_meta_data = meta_data.copy()
                # new_meta_data["run_tag"] = info.run_tag
                # # Write new meta file to include the run tag
                # if meta_data.get("run_tag")== None:
                #     with open(meta_file, "w") as file:
                #         json.dump(new_meta_data, file, indent=4)
            
            truncate_event_front = 1000 #index to truncate the events before
            truncate_event_back = 500 #index to truncate the events after

            if os.path.exists(config_file) and (info.number_of_events > (truncate_event_front + truncate_event_back)):
                    
                    start_index, end_index = truncate_event_front, info.number_of_events - truncate_event_back -1 #first 1000 events are noisy # the last 500 events might be empty

                    config = configparser.ConfigParser()
                    config.optionxform = str
                    config.read(config_file)

                    info.record_length = int(config.get("COMMON", "RECORD_LENGTH"))

                    process_config = {"nchs": info.number_of_channels,
                    "nsamps": info.record_length,
                    "sample_selection": info.baseline_n_samples, 
                    "samples_to_average": info.baseline_n_samples_avg}

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
                        info.n_processed_events = int(len(wfp.baseline_rms))

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
    chunk_size = 100

    # Check if the existing DataFrame has the same number of columns as the new data
    length_existing_df = 0 if existing_df is None else len(existing_df.columns)
    print("Number of columns match? ", (length_existing_df == n_columns))
    
    # Convert the data_files list to a numpy array for faster processing
    data_files = np.array(data_files)

    # If not reprocessing, filter out the files that are already in the existing DataFrame
    if (not reprocess) and (existing_df is not None) and (length_existing_df == n_columns): 
        path_array = np.array(existing_df["file_path"].unique())
        data_files = data_files[~np.in1d(data_files, path_array)] # Filter out the files that are already processed
    elif (len(data_files) != 0):
        print(f"Processing {len(data_files)} new files")
        data_df = pd.DataFrame(columns=info.__dict__.keys())
        data_df.iloc[:0].to_csv(RUN_INFO_FILE, index=False)
    else:
        print("No new files to process")
        return
    
    # Just to check if the data_files are being processed correctly
    for data_file in data_files:

        try:
            data = single_data_file_to_dict(data_file) # Convert the chunk of data
            # data = data[data != np.array(None)] # Remove any None values
        except Exception as e:
            print(f"Error processing data: {e}")
            continue

        # Create a DataFrame from the new data -> csv; write to file in append mode
        if data != None:
            new_df = pd.DataFrame.from_dict([data])
            new_df.to_csv(RUN_INFO_FILE, mode='a', index=False, header=False)

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