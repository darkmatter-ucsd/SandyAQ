'''
This is a tool to unify, if possible and desired, the data format of the meta-data json files.
'''


import os
import glob
import json
import re
import numpy as np
import sys
import datetime
import configparser


DATA_FOLDERS = [
    "/home/daqtest/DAQ/SandyAQ/softlink_to_data/all_data_new/202410_LXe_new/",
    # Add more data folders as needed, need to be an absolute path
]

class Info:
    def __init__(self, channel, threshold, date, time):
        self.channel = channel
        self.threshold = threshold
        self.date = date
        self.time = time


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

    else:
        match = re.match(r"meta_config_all_(\d{8})_(\d{6})\.json", data_file)

        if match:
            date, time = match.groups()
            channel, threshold = None, None
        
        else:
            print(f"File name {data_file} does not match the pattern")

            return None
        
    meta_data_info = Info(channel, threshold, date, time)
        
    return meta_data_info


v_meta_data_from_file_name = np.vectorize(get_meta_data_from_file_name, otypes=[np.ndarray])

v_basename = np.vectorize(os.path.basename, otypes=[np.ndarray])
v_dirname = np.vectorize(os.path.dirname, otypes=[np.ndarray])

### step 1: create new meta data file (to be replaced in step 2)
### check if everything make sense in the new meta data

def step_1_add_items():
    
    # Check if "DATA_FOLDERS" is an aboslute path for a directory
    for data_folder in DATA_FOLDERS:
        if not os.path.isabs(data_folder) and not os.path.isdir(data_folder):
            raise ValueError(f"{data_folder} is not an absolute path for a directory")

    # Get the list of data files from DATA_FOLDERS
    data_files_name = get_data_files(DATA_FOLDERS, pattern="meta_config*.json")
    print(f"Found {len(data_files_name)} meta data files in {DATA_FOLDERS}")

    file_name = v_basename(data_files_name)
    dir_name = v_dirname(data_files_name)

    #turn all list into np.array
    data_files_name = np.array(data_files_name) # path + file name
    file_name = np.array(file_name)
    dir_name = np.array(dir_name)
    
    assert(len(file_name)==len(dir_name))

    for i in range(len(file_name)):
        
        data_file = data_files_name[i]
        print(f"Processing {data_file}")

        with open(data_file, "r") as file:
            meta_data = json.load(file)

        new_meta_data = meta_data.copy()
        rewrite_bool = False
        # if DC_OFFSET is not in the meta data, add it
        if "DC_OFFSET" not in new_meta_data:
            new_meta_data["DC_OFFSET"] = "+40"
            rewrite_bool = True

        if "data_taking_mode" not in new_meta_data:
            new_meta_data["data_taking_mode"] = ""
            rewrite_bool = True

        if "post_trigger" not in new_meta_data:
            new_meta_data["post_trigger"] = int(60)
            rewrite_bool = True

        if rewrite_bool:
            new_file_name = os.path.join(dir_name[i], f"new_{file_name[i]}")
            with open(new_file_name, "w") as file:
                json.dump(new_meta_data, file, indent=4)

def step_1_edit_item():
    
    # Check if "DATA_FOLDERS" is an aboslute path for a directory
    for data_folder in DATA_FOLDERS:
        if not os.path.isabs(data_folder) and not os.path.isdir(data_folder):
            raise ValueError(f"{data_folder} is not an absolute path for a directory")

    # Get the list of data files from DATA_FOLDERS
    data_files_name = get_data_files(DATA_FOLDERS, pattern="meta_config*.json")
    print(f"Found {len(data_files_name)} meta data files in {DATA_FOLDERS}")

    file_name = v_basename(data_files_name)
    dir_name = v_dirname(data_files_name)

    #turn all list into np.array
    data_files_name = np.array(data_files_name) # path + file name
    file_name = np.array(file_name)
    dir_name = np.array(dir_name)
    
    assert(len(file_name)==len(dir_name))

    for i in range(len(file_name)):
        
        data_file = data_files_name[i]
        print(f"Processing {data_file}")

        with open(data_file, "r") as file:
            meta_data = json.load(file)

        new_meta_data = meta_data.copy()

        new_meta_data["data_taking_mode"] = "all_channels"

        new_meta_data["board_0_channels"] = np.arange(0,16).tolist()
        new_meta_data["board_1_channels"] = np.arange(16,24).tolist()

        new_file_name = os.path.join(dir_name[i], f"new_{file_name[i]}")
        with open(new_file_name, "w") as file:
            json.dump(new_meta_data, file, indent=4)

def step_1_edit_item_from_config():
    
    # Check if "DATA_FOLDERS" is an aboslute path for a directory
    for data_folder in DATA_FOLDERS:
        if not os.path.isabs(data_folder) and not os.path.isdir(data_folder):
            raise ValueError(f"{data_folder} is not an absolute path for a directory")

    # Get the list of data files from DATA_FOLDERS
    data_files_name = get_data_files(DATA_FOLDERS, pattern="meta_config*.json")
    print(f"Found {len(data_files_name)} meta data files in {DATA_FOLDERS}")

    file_name = v_basename(data_files_name)
    dir_name = v_dirname(data_files_name)
    meta_data_info = v_meta_data_from_file_name(file_name)

    #turn all list into np.array
    data_files_name = np.array(data_files_name) # path + file name
    file_name = np.array(file_name)
    dir_name = np.array(dir_name)

    assert(len(file_name)==len(dir_name))

    for i in range(len(file_name)):

        data_file = data_files_name[i]
        print(f"Processing {data_file}")

        with open(data_file, "r") as file:
            meta_data = json.load(file)
        new_meta_data = meta_data.copy()

        # remove all "DC_offset" key from new_meta_data
        if "DC_offset" in new_meta_data:
            del new_meta_data['DC_offset']

        # get the channel number for each board
        if meta_data_info[i].channel != None:
            
            config_file_path = os.path.join(dir_name[i], "DAQ_config/", f"config_{meta_data_info[i].channel}_{meta_data_info[i].threshold}.ini")
            # Check if the config file exists
            if not os.path.isfile(config_file_path):
                raise ValueError(f"Config file {config_file_path} does not exist")
            
            # Read the config file
            config = configparser.ConfigParser()
            config.read(config_file_path)

            new_meta_data["data_taking_mode"] = "single_channel"
            
            new_meta_data["post_trigger"] = float(config.get("BOARD-0", "POST_TRIGGER"))
            
            test_channel = 0
            # try different channel on board until we find the DC_OFFSET
            while(test_channel < 16):
                if config.has_option(f"BOARD-0_CHANNEL-{test_channel}", "DC_OFFSET"):
                    new_meta_data["DC_OFFSET"] = config.get(f"BOARD-0_CHANNEL-{test_channel}", "DC_OFFSET")
                    board_number = 0
                    break

                if config.has_option(f"BOARD-1_CHANNEL-{test_channel}", "DC_OFFSET"):
                    new_meta_data["DC_OFFSET"] = config.get(f"BOARD-1_CHANNEL-{test_channel}", "DC_OFFSET")
                    board_number = 1
                    break

                test_channel += 1   

            channel_list = config.get(f"BOARD-{board_number}", "CHANNEL_LIST")
            if (len(channel_list) == 0):
                raise ValueError(f"CHANNEL_LIST is empty in {config_file_path}")
            channel_list = channel_list.split(" ")
            channel_list = [int(x) for x in channel_list]
            new_meta_data[f"board_{board_number}_channels"] = channel_list

            new_file_name = os.path.join(dir_name[i], f"new_{file_name[i]}")
            with open(new_file_name, "w") as file:
                json.dump(new_meta_data, file, indent=4)

        elif meta_data_info[i].channel == None:
            
            config_file_path = os.path.join(dir_name[i], "DAQ_config/", f"config_all_{meta_data_info[i].date}_{meta_data_info[i].time}.ini")
            # Check if the config file exists
            if not os.path.isfile(config_file_path):
                config_file_path = os.path.join(dir_name[i], "DAQ_config/", f"config_all.ini")

                if not os.path.isfile(config_file_path):
                    raise ValueError(f"Config file {config_file_path} does not exist")
            
            # Read the config file
            config = configparser.ConfigParser()
            config.read(config_file_path)

            new_meta_data["data_taking_mode"] = "all_channels"
            
            new_meta_data["post_trigger"] = int(config.get("BOARD-0", "POST_TRIGGER"))
            
            new_meta_data["DC_OFFSET"] = config.get(f"BOARD-0_CHANNEL-0", "DC_OFFSET")

            channel_list = config.get(f"BOARD-0", "CHANNEL_LIST")
            if (len(channel_list) > 0):
                channel_list = channel_list.split(" ")
                channel_list = [int(x) for x in channel_list]
                new_meta_data["board_0_channels"] = channel_list
                n_channel_board_0 = len(channel_list)
            
            channel_list = config.get(f"BOARD-1", "CHANNEL_LIST")
            if (len(channel_list) > 0):
                channel_list = channel_list.split(" ")
                channel_list = [int(x) + n_channel_board_0 for x in channel_list]
                new_meta_data["board_1_channels"] = channel_list

            new_file_name = os.path.join(dir_name[i], f"new_{file_name[i]}")
            with open(new_file_name, "w") as file:
                json.dump(new_meta_data, file, indent=4)

        else:
            raise ValueError("Channel number has wrong format")
    
def step1_add_runtime():

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
                
# replace the old meta data file by the new ones
def step_2_replace_meta():
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
    # step_1_edit_item()
    # step_1_edit_item_from_config()
    # step_1_add_items()
    # step_1_add_record_length()
    step_2_replace_meta()