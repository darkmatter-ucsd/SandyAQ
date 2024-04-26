"""
This wrapper is used to take single channel calibration data. It does the following steps:
- Generate temporary config files based on the config template and user inputs (data_taking_settings)
- run sandyaq to take data according to the temp config file
- write the user inputs as metadata 
"""

import os
import configparser
import datetime
import json
from copy import deepcopy
from tqdm import tqdm

class SingleCalibration:
    def __init__(self, data_taking_settings, config_template_path = "/home/daqtest/DAQ/SandyAQ/sandyaq/config/config_template.ini"):
        # check if the data_taking_settings is a dictionary, and have all of the required keys
        if not isinstance(data_taking_settings, dict):
            raise ValueError("data_taking_settings should be a dictionary")
        if not all(key in data_taking_settings for key in ["channel_threshold_dict",
                                                           "number_of_events",
                                                           "output_folder", 
                                                           "voltage_config", 
                                                           "temperature"]):
            raise ValueError("data_taking_settings should have all of the required keys: \
                             channel_threshold_dict, number_of_events, output_folder, voltage_config, temperature")
        self.data_taking_settings = data_taking_settings

        # check if the config_template is a string and exists
        if not isinstance(config_template_path, str):
            raise ValueError("config_template should be a string")
        if not os.path.exists(config_template_path):
            raise ValueError("config_template does not exist")
        
        # load the config template
        self.config_template = configparser.ConfigParser()
        self.config_template.optionxform = str
        self.config_template.read(config_template_path)
        self.tmp_config_files = self.generate_temp_configs()

    def generate_temp_configs(self):
        # the template config is an ini file. We need to do the following modifications:
        # 1. add the channel list
        # 2. add the thresholds

        # first: make a tmp folder to store the temp config files
        temp_folder = os.path.join(self.data_taking_settings["output_folder"], "tmp")
        if not os.path.exists(temp_folder):
            os.makedirs(temp_folder)
        tmp_config_files = []
        for channel in self.data_taking_settings["channel_threshold_dict"].keys():
            new_config_path = os.path.join(temp_folder, f"config_{channel}_{self.data_taking_settings['channel_threshold_dict'][channel]}.ini")

            # skip if the config file already exists
            if os.path.exists(new_config_path):
                print(f"Config file {new_config_path} already exists. Reading from the file.")
                tmp_config_files.append(new_config_path)
                continue

            # calculate the board number
            if channel <= 15:
                board_number = 0
                local_channel = channel
            else:
                board_number = 1
                local_channel = channel - 16
            # then modify the config template
            new_config = deepcopy(self.config_template)
            new_config.set(f"BOARD-{board_number}", "CHANNEL_LIST", f"{local_channel}")

            section_name = f'BOARD-{board_number}_CHANNEL-{local_channel}'
            if not new_config.has_section(section_name):
                new_config.add_section(section_name)

            # Add the new configuration to the BOARD-0 section
            new_config.set(section_name, 'DC_OFFSET', '+40')
            new_config.set(section_name, 'TRIGGER_THRESHOLD', f'{self.data_taking_settings["channel_threshold_dict"][channel]}')
            new_config.set(section_name, 'CHANNEL_TRIGGER', 'ACQUISITION_ONLY')
            new_config.set(section_name, 'PULSE_POLARITY', '1')

            # write the new config to a file. The file name is the channel number and the threshold
            with open(new_config_path, "w") as f:
                new_config.write(f)
            tmp_config_files.append(new_config_path)
        return tmp_config_files
    
    def run(self, dry_run = False):
        for tmp_config_file in tqdm(self.tmp_config_files):
            # -c: config file
            # -n: number of events
            # -d: output folder
            # -f: file name

            # extract the file name from the tmp config file
            data_file_name = os.path.basename(tmp_config_file).replace(".ini", "")
            # get the current timestamp, and add it to the file name
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            data_file_name = f"{data_file_name}_{timestamp}"
            meta_file_name = os.path.join(self.data_taking_settings["output_folder"], f"meta_{data_file_name}.json")

            with open(meta_file_name, "w") as f:
                json.dump(self.data_taking_settings, f)


            # run sandyaq to take data
            # the executable is in: /home/daqtest/DAQ/SandyAQ/sandyaq/build

            run_sandyaq_command = "/home/daqtest/DAQ/SandyAQ/sandyaq/build/sandyaq"

            if not dry_run:
                try:
                    print(f"Taking data with config file: {tmp_config_file}")
                    os.system(f"{run_sandyaq_command} -c {tmp_config_file} -n {self.data_taking_settings['number_of_events']} -d {self.data_taking_settings['output_folder']} -f {data_file_name}")
                except Exception as e:
                    print(f"Error running sandyaq: {e}")
            else:
                print(f"Running sandyaq -c {tmp_config_file} -n {self.data_taking_settings['number_of_events']} -d {self.data_taking_settings['output_folder']} -f {data_file_name}")
            
        
        

            


