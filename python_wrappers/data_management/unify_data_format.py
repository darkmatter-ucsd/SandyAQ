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

def get_data_files(data_directories, pattern="meta_config*.json"):
    """
    Get all the data files in the given data directories
    Also search subdirectories
    """
    data_files = []
    for data_directory in data_directories:
        data_files.extend(glob.glob(os.path.join(data_directory, f"**/{pattern}"), recursive=True))

    return data_files
    
def get_meta_data_from_file_name(data_file):
    """
    Get the meta data from the file name
    """
    
    match = re.match(r"meta_config_(\d+)_(\d+)_(\d{8})_(\d{6})\.json", data_file)

    # Extract the basic identifier information from the file name that matches the pattern
    if match:
        channel, threshold, date, time = match.groups()
        channel = int(channel)
        threshold = int(threshold)

        return channel, threshold, date, time
    else:
        print(f"File name {data_file} does not match the pattern")
        return None

v_meta_data_from_file_name = np.vectorize(get_meta_data_from_file_name)

v_basename = np.vectorize(os.path.basename)
v_dirname = np.vectorize(os.path.dirname)



def step1():

    # Check if "DATA_FOLDERS" is an aboslute path for a directory
    for data_folder in DATA_FOLDERS:
        if not os.path.isabs(data_folder) and not os.path.isdir(data_folder):
            raise ValueError(f"{data_folder} is not an absolute path for a directory")

    # Get the list of data files from DATA_FOLDERS
    data_files_name = get_data_files(DATA_FOLDERS)
    print(f"Found {len(data_files_name)} data files in {DATA_FOLDERS}")

    file_name = v_basename(data_files_name)
    dir_name = v_dirname(data_files_name)
    channel, threshold, date, time = v_meta_data_from_file_name(file_name)

    #turn all list into np.array
    data_files_name = np.array(data_files_name) # path + file name
    file_name = np.array(file_name)
    dir_name = np.array(dir_name)
    channel = np.array(channel)
    threshold = np.array(threshold)
    date = np.array(date)
    time = np.array(time)

    date_time = np.array([f"{d}_{t}" for d, t in zip(date, time)])
    unique_id = np.array([f"{dir}!!!{dt}" for dir, dt in zip(dir_name, date_time)])
    unique_id = np.unique(unique_id)

    for id in unique_id:

        unique_path, unique_date_time = id.split("!!!")

        # create mask
        mask = (dir_name == unique_path) & (date_time == unique_date_time)

        # after filtering with mask, sort the data_files by channel
        sorted_data_file = data_files_name[mask][channel[mask].argsort()]

        if len(sorted_data_file) < 2:
            print(f"Found less than 2 files for {id}")
            continue
        
        print(f"Loading {sorted_data_file[0]}")
        with open(sorted_data_file[0], "r") as file:
            first_meta_data = json.load(file)
                        
        previous_runtime = first_meta_data.get("runtime")

        if previous_runtime is not None:
            previous_runtime = datetime.datetime.strptime(previous_runtime, "%H:%M:%S.%f")

            for data_file in sorted_data_file[1:]:

                print(f"Processing {data_file}")

                with open(data_file, "r") as file:
                    meta_data = json.load(file)
                
                _runtime = datetime.datetime.strptime(meta_data.get("runtime"), "%H:%M:%S.%f")

                new_runtime = _runtime - previous_runtime

                new_meta_data = meta_data.copy()
                new_meta_data["runtime"] = str(new_runtime)

                _base_name = os.path.basename(data_file)
                _path_name = os.path.dirname(data_file)
                new_file_name = os.path.join(_path_name, f"new_{_base_name}")

                with open(new_file_name, "w") as file:
                    json.dump(new_meta_data, file, indent=4)

                previous_runtime = _runtime
                

def step2():
    # Check if "DATA_FOLDERS" is an aboslute path for a directory
    for data_folder in DATA_FOLDERS:
        if not os.path.isabs(data_folder) and not os.path.isdir(data_folder):
            raise ValueError(f"{data_folder} is not an absolute path for a directory")

    # Get the list of data files from DATA_FOLDERS
    data_files_name = get_data_files(DATA_FOLDERS, pattern="new_meta_config*.json")
    print(f"Found {len(data_files_name)} data files in {DATA_FOLDERS}")

    # Replace the "meta_config_..." by "new_meta_config_..." 
    for data_file in data_files_name:
        existing_data_file = data_file.replace("new_meta_config_", "meta_config_")

        # remove the existing "meta_config_..." file
        os.remove(existing_data_file)

        # rename the "new_meta_config_..." to "meta_config_..."
        print(f"Renaming {data_file} to {existing_data_file}")
        os.rename(data_file, existing_data_file)

if __name__ == "__main__":
    step2()