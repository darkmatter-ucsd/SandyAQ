"""
This wrapper is used to take single channel calibration data. It does the following steps:
- Generate temporary config files based on the config template and user inputs (data_taking_settings)
- run calibration runs with sandyaq
- run sandyaq to take data according to the temp config file
- write the user inputs as metadata 
"""

import os
import configparser
import datetime
import json
from copy import deepcopy
from tqdm import tqdm
import glob
import numpy as np
import sys
import configparser
import json

import threading
import time
import subprocess

current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0,os.path.join(current_dir,"../"))
import common.utils as util
import data_processing.waveform_processor as waveform_processor
import common.config_reader as common_config_reader

sys.path.insert(0,"/home/daqtest/Processor/sandpro")
import sandpro

class SingleChannel_DataTaking:

    def __init__(self, data_taking_settings, 
                 config_template_path = "/home/daqtest/DAQ/SandyAQ/sandyaq/config/config_template.ini", 
                 calibration = True,
                 same_threshold = True):
        
        self.common_cfg_reader = common_config_reader.ConfigurationReader()
        self.config = self.common_cfg_reader.get_data_taking_config()

        self.DAQ_module = self.config.get('DAQ_MODULE', 'DAQ')
        self.bit_of_daq = int(self.config.get(self.DAQ_module, 'n_bits'))
        self.vpp = float(self.config.get(self.DAQ_module, 'range'))
        
        self.DC_offset = self.config.get('DATA_TAKING_SETTINGS', 'DC_offset')
        self.guessed_baseline_mV = float(self.config.get('DATA_TAKING_SETTINGS', 'guessed_baseline_mV'))
        
        self.same_threshold = same_threshold
        self.run_sandyaq_command = "/home/daqtest/DAQ/SandyAQ/sandyaq/build/sandyaq"
        
        # check if the data_taking_settings is a dictionary, and have all of the required keys
        if not isinstance(data_taking_settings, dict):
            raise ValueError("data_taking_settings should be a dictionary")
        
        if not all(key in data_taking_settings for key in ["number_of_events",
                                                           "output_folder", 
                                                           "voltage_config", 
                                                           "temperature",
                                                           "threshold_multiplier",
                                                           "channel_list"]):
            raise ValueError("data_taking_settings should have all of the required keys: \
                              number_of_events, output_folder, voltage_config, temperature, threshold_multiplier")
        self.user_input_data_taking_setting = data_taking_settings
        self.threshold_multiplier = self.user_input_data_taking_setting["threshold_multiplier"] * np.ones(24)
        self.timeout = 1800 # in second; kill run after this time

        # calibration settings
        self.n_calibration_events = 3000 # number - 500
        self.calibration_start_index = 2000 # cannot be lower than 2000
        self.calibration_timeout = 60 # in second; kill run after this time

        # check if the config_template is a string and exists
        if not isinstance(config_template_path, str):
            raise ValueError("config_template should be a string")
        if not os.path.exists(config_template_path):
            raise ValueError("config_template does not exist")
        
        # load the config template
        self.config_template = configparser.ConfigParser()
        self.config_template.optionxform = str
        self.config_template.read(config_template_path)

        # generate the data taking settings for both calibration and data taking
        self._gen_data_taking_settings()

        if calibration == True:
            self.run_calibration()
        elif (type(calibration)==str):
            if (os.path.isdir(calibration)):
                self.update_adc_threshold_from_path(calibration)
            elif (os.path.isfile(calibration)):
                raise NotADirectoryError("Please specify a path to directory instead")
            else:
                raise FileNotFoundError(f"{calibration} not found")
        elif calibration == False:
            # directly generate the temporary config files from user input
            self.tmp_config_files = self._gen_tmp_configs()
        else:
            raise TypeError
            
    def _gen_data_taking_settings(self):

        self.data_taking_settings = self.user_input_data_taking_setting.copy()
        self.data_taking_settings["timeout"] = self.timeout
        
        self.calib_data_taking_settings = self.user_input_data_taking_setting.copy()
        # set a very low threshold for all channels, to take noise data
        # data_settings["channel_threshold_dict"] = {0:2305,1:2269,2:2200,3:2209,4:2378,5:2274,6:2386,7:2516,8:2627,9:2316,10:2162,11:2066,12:2456,13:2446,14:2413,15:2192,16:2230,17:2468,18:2158,19:2090,20:2342,21:2258,22:2313,23:2266}
        # self.calib_data_taking_settings["channel_threshold_dict"] = {0:2297,1:2269,2:2200,3:2209,4:2390,5:2274,6:2386,7:2516,8:2585,9:2305,10:2162,11:2066,12:2414,13:2446,14:2277,15:2192,16:2230,17:2468,18:2158,19:2090,20:2280,21:2258,22:2313,23:2233} 
        # self.calib_data_taking_settings["channel_threshold_dict"] = {0:2297,1:2369,2:2400,3:2360,4:2390,5:2274,6:2386,7:2516,8:2585,9:2305,10:2300,11:2066,12:2414,13:2446,14:2277,15:2192,16:2230,17:2468,18:2158,19:2090,20:2280,21:2258,22:2313,23:2233} # 106 deg
        # self.calib_data_taking_settings["channel_threshold_dict"] = {0:2297,1:2369,2:2400,3:2300,4:2390,5:2274,6:2386,7:2516,8:2585,9:2305,10:2294,11:2358,12:2414,13:2446,14:2277,15:2292,16:2300,17:2468,18:2258,19:2190,20:2280,21:2258,22:2413,23:2233} # 106 deg
        # self.calib_data_taking_settings["channel_threshold_dict"] = {0:2395,1:2380,2:2509,3:2327,4:2480,5:2391,6:2501,7:2596,8:2821,9:2363,10:2304,11:2169,12:2500,13:2537,14:2479,15:2329,16:2362,17:2632,18:2273,19:2214,20:2368,21:2346,22:2447,23:2354} # 106 deg
        # self.calib_data_taking_settings["channel_threshold_dict"] = {0:550,1:560,2:570,3:510,4:690,5:530,6:700,7:825,8:825,9:550,10:500,11:340,12:740,13:810,14:620,15:520,16:570,17:710,18:420,19:420,20:580,21:580,22:630,23:450}
        
        guess_threshold = 700 + util.mv_to_adc(float(self.guessed_baseline_mV), DCOFFSET=int(self.DC_offset), vpp=float(self.vpp), bit_of_daq=int(self.bit_of_daq))
        threshold_dict = {i:int(guess_threshold) for i in self.user_input_data_taking_setting["channel_list"]}
        self.calib_data_taking_settings["channel_threshold_dict"] = threshold_dict

        print(threshold_dict)
        
        self.calib_data_taking_settings["number_of_events"] = self.n_calibration_events
        self.calib_data_taking_settings["output_folder"] = self.user_input_data_taking_setting["output_folder"] + "/threshold_calibration"
        self.calib_data_taking_settings["run_tag"] = "threshold_calibration"
        self.calib_data_taking_settings["threshold_multiplier"] = 1.0
        self.calib_data_taking_settings["timeout"] = self.calibration_timeout
        
        return 

    def _gen_tmp_configs(self, calibration = False):
        # the template config is an ini file. We need to do the following modifications:
        # 1. add the channel list
        # 2. add the thresholds

        # create a separate set of config from the given config for the threshold calibration

        if calibration:
            data_taking_settings = self.calib_data_taking_settings
        else:
            data_taking_settings = self.data_taking_settings

        temp_folder = os.path.join(data_taking_settings["output_folder"], "tmp")

        # first: make a tmp folder to store the temp config files
        if not os.path.exists(temp_folder):
            os.makedirs(temp_folder)
            
        tmp_config_files = []
        for channel in data_taking_settings["channel_list"]:
            new_config_path = os.path.join(temp_folder, f"config_{channel}_{data_taking_settings['channel_threshold_dict'][channel]}.ini")

            # skip if the config file already exists
            if os.path.exists(new_config_path):
                print(f"Config file {new_config_path} already exists. Reading from the file.")
                tmp_config_files.append(new_config_path)
                continue

            # calculate the board number
            if channel <= 11:
                board_number = 0
                local_channel = channel
            else:
                board_number = 1
                local_channel = channel - 12
            # then modify the config template
            new_config = deepcopy(self.config_template)
            new_config.set(f"BOARD-{board_number}", "CHANNEL_LIST", f"{local_channel}")
            new_config.set(f"BOARD-{board_number}", "POST_TRIGGER", f"{0.9}")
            

            section_name = f'BOARD-{board_number}_CHANNEL-{local_channel}'
            if not new_config.has_section(section_name):
                new_config.add_section(section_name)

            # Add the new configuration to the BOARD-0 section
            new_config.set(section_name, 'DC_OFFSET', str(self.DC_offset))
            new_config.set(section_name, 'TRIGGER_THRESHOLD', f'{data_taking_settings["channel_threshold_dict"][channel]}')
            new_config.set(section_name, 'CHANNEL_TRIGGER', 'ACQUISITION_ONLY')
            new_config.set(section_name, 'PULSE_POLARITY', '1')
            # new_config.set(section_name, 'N_EVENTS', f'{data_settings["number_of_events"]}')

            # write the new config to a file. The file name is the channel number and the threshold
            with open(new_config_path, "w") as f:
                new_config.write(f)
            tmp_config_files.append(new_config_path)
            
        return tmp_config_files
    
    def _metadata_checklist(self, data_taking_settings):
        # check if the dictionary have all the essential entries before writing
        # prevent changes in the code messing up with the recording of meta_data_file
        try:
            assert(data_taking_settings["runtime"] != None)
            assert(data_taking_settings["record_length"]!= None)
            assert(data_taking_settings["start_timestamp"]!= None)
            assert(data_taking_settings["timeout"]!= None)
            assert(data_taking_settings["comment"]!= None)
            assert(data_taking_settings["number_of_events"]!= None)
            assert(data_taking_settings["run_tag"]!= None)
        except Exception as e:
            print(f"Required metadata entry {e} is missing! Please check the code. ")
            raise
        
    def get_list_metadata_from_folder(self, data_folder, channels = np.arange(0,24)):
        '''
        Inside the given data_folder, generate a list of metadata_file with the latest
        metadata_file for each channel. channels can be specified
        '''
        
        metadata_list = []
        for channel in channels:
            # search the metadata file for that channel
            tmp_list = glob.glob(f"{data_folder}/meta_config_{channel}_*")
            
            # check if any file exist
            if len(tmp_list)==0:
                raise FileNotFoundError(f"Cannot find any meta_config_ file for channel {channel}")
            
            # if only one file is found
            elif len(tmp_list)==1:
                metadata_list.append(tmp_list[0])
            
            # if more than one file is found, use the latest file 
            elif len(tmp_list) > 1:
                sorted_tmp_list = sorted(tmp_list, key=util.extract_date_meta_data)
                metadata_list.append(sorted_tmp_list[-1])
        
        # check if the array size is correct
        try:
            assert(len(metadata_list)==len(channels))
        except AssertionError as e:
            raise( AssertionError( "Number of metadata_list is not the same as channel input. " + \
                                   "Bug in the code, please check.") )
        
        return metadata_list
        
    def get_adc_threshold_from_calibration(self, data_folder, metadata_list):

        baseline_mean_V_array = []
        baseline_std_V_array = []
        channels = []

        for i, meta_data in enumerate(metadata_list):
            print(metadata_list[i])
            # meta_data = sorted_meta_data_list[i]
            meta_data_basename = os.path.basename(meta_data)
            parts = meta_data_basename.split('_')
            config_name = "_".join(parts[1:4]) + ".ini"
            channel = int(parts[2])

            print(config_name)
            config_path = os.path.join(data_folder, "tmp", config_name)
            config = configparser.ConfigParser()
            config.optionxform = str
            config.read(config_path)

            process_config = {"nchs": 1,
                "nsamps": int(config.get("COMMON", "RECORD_LENGTH")),
                "sample_selection": 120,
                "samples_to_average": 40
                }   
            
            # dump the config to a json file
            with open("tmp_process_config.json", "w") as f:
                json.dump(process_config, f)
            if len(config.get("BOARD-0", "CHANNEL_LIST")) > 0:
                board_number = 0
            else:
                board_number = 1

            processor= sandpro.processing.rawdata.RawData(config_file = "tmp_process_config.json",
                                                perchannel=False)
            data_file_basename = meta_data_basename.replace("meta_", "").replace(".json", f"_board_{board_number}.bin")
            try:
                data = processor.get_rawdata_numpy(n_evts=self.n_calibration_events-1,
                                            file=os.path.join(data_folder, data_file_basename),
                                            bit_of_daq=14,
                                            headersize=4,inversion=False)
                start_index, end_index = self.calibration_start_index, self.n_calibration_events-1-500
            except Exception as e:
                print(e)
                data = processor.get_rawdata_numpy(n_evts=200,
                                            file=os.path.join(data_folder, data_file_basename),
                                            bit_of_daq=14,
                                            headersize=4,inversion=False)
                start_index, end_index = 0, 119
            
            wfp = waveform_processor.WFProcessor(data_folder, volt_per_adc=2/2**14)
            wfp.set_data(data["data_per_channel"][start_index:end_index,0], in_adc = False)
            wfp.process_wfs()
            
            baseline_std_V = np.mean(wfp.baseline_std_V)
            baseline_mean_V = np.mean(wfp.baseline_mean_V)
            baseline_mean_V_array.append(baseline_mean_V)
            baseline_std_V_array.append(baseline_std_V)
            channels.append(channel)

        baseline_mean_V_array = np.array(baseline_mean_V_array)
        baseline_std_V_array = np.array(baseline_std_V_array)

        # threshold_mV = (baseline_mean_V_array + 2 * (2 * np.sqrt(2) * baseline_std_V_array)) * 1000
        threshold_mV = (baseline_mean_V_array + self.threshold_multiplier[channels] * baseline_std_V_array) * 1000
        threshold_adc = util.v_mv_to_adc(threshold_mV)
        
        # test change
        max_threshold_adc = util.v_mv_to_adc((baseline_mean_V_array + self.threshold_multiplier[channels] * np.max(baseline_std_V_array)) * 1000)
        # max_threshold_adc = np.max(threshold_adc) * np.ones(len(threshold_adc))

        if self.same_threshold:
            threshold_dict = {i:int(thres) for i, thres in enumerate(max_threshold_adc.astype(int))}
        else:
            threshold_dict = {i:int(thres) for i, thres in enumerate(threshold_adc.astype(int))}


        return threshold_dict
   
    # for multi-threading and timeout
    def _run_executable(self, e, tmp_config_file, number_of_events, base_path, data_file_name):
        # os.system(f"{self.run_sandyaq_command} -c {tmp_config_file} -n {self.data_taking_settings['number_of_events']} -d {base_path} -f {data_file_name}")
        # if e.isSet():
        #     print("Timeout")
        #     os.system(f"pkill -f {self.run_sandyaq_command}")

        print("Running sandyaq")
        process = subprocess.Popen(
            [self.run_sandyaq_command, '-c', tmp_config_file, '-n', str(number_of_events), '-d', base_path, '-f', data_file_name],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        

        # Check for timeout
        while process.poll() is None:
            if e.is_set():
                process.terminate()  # Gracefully terminate the process
                print("Timeout")
                break
            time.sleep(1)  # Check every second

        # Wait for the process to terminate if it hasn’t been terminated already
        process.wait()

        if process.returncode != 0:
            print(f"Process terminated with errors: {process.stderr.read().decode()}")
   
    def update_adc_threshold_from_path(self, calibration_path):
        print(f"Setting threshold from folder {calibration_path}...")
        
        # self.calib_data_taking_settings["output_folder"] = calibration_path
        metadata_list = self.get_list_metadata_from_folder(calibration_path, 
                                                           self.user_input_data_taking_setting["channel_list"])
        
        self.data_taking_settings["channel_threshold_dict"] = self.get_adc_threshold_from_calibration(calibration_path, metadata_list)
        # self.tmp_config_files = self._gen_tmp_configs(calibration=False)
        
        return
    
    def run_calibration(self, dry_run = False):
        print("Running calibration...")
        
        # settings for the calibration run
        self.tmp_config_files = self._gen_tmp_configs(calibration=True)
        self.run(dry_run=False, calibration=True)

        # get threshold
        print("Determining thresholds from calibration run...")
        calibration_path = self.calib_data_taking_settings["output_folder"]
        self.update_adc_threshold_from_path(calibration_path)
        
        return 
    
    def run(self, dry_run = False, calibration = False, set_timeout = False):
        
        
        if dry_run: # This is not doing anything?? -> Yue
                print(f"Running sandyaq -c {tmp_config_file} -n {self.data_taking_settings['number_of_events']} -d {base_path} -f {data_file_name}")
                raise ValueError("Dry run not implemented yet. Please set dry_run to False. Exiting...")
        
        if calibration:
            data_taking_settings = self.calib_data_taking_settings
        else:
            self.tmp_config_files = self._gen_tmp_configs(calibration=False)
            data_taking_settings = self.data_taking_settings
        
        # get the current timestamp (global to all channel for the same run), and add it to the file name
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

        base_path = data_taking_settings["output_folder"]
        number_of_events = data_taking_settings["number_of_events"]
        # meta_file_name = os.path.join(base_path, f"meta_{data_file_name}.json")
        
        # runtime_csv_file = os.path.join(base_path, f"runtime_all_channel_{timestamp}.csv")
        # with open(runtime_csv_file, "w") as f:
        #         f.write("channel,elapsed_time\n")

        # run sandyaq to take data
        # the executable is in: /home/daqtest/DAQ/SandyAQ/sandyaq/build
        # run_sandyaq_command = "/home/daqtest/DAQ/SandyAQ/sandyaq/build/sandyaq"
        for tmp_config_file in tqdm(self.tmp_config_files):
            # -c: config file
            # -n: number of events
            # -d: output folder
            # -f: file name

            parts = tmp_config_file.split('/')[-1].split('_')
            channel = int(parts[1])

            # extract the file name from the tmp config file
            data_file_name = os.path.basename(tmp_config_file).replace(".ini", "")
            # get the current timestamp, and add it to the file name
            # moved this out of the loop: so that all channel from the same run has the same timestamp
            # timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            data_file_name = f"{data_file_name}_{timestamp}"
            
            start_timestamp = datetime.datetime.now()

            print(f"Taking data with config file: {tmp_config_file}")
            
            if set_timeout:
                e = threading.Event()
                exit_current_loop = False

                # start a thread to run the executable
                t = threading.Thread(target=self._run_executable, args=(e, tmp_config_file, number_of_events, base_path, data_file_name))
                
                t.start()
                t.join(timeout=data_taking_settings["timeout"])

                if t.is_alive():
                    e.set()
                    t.join()
                    print("Timeout occurred and process terminated")

                    # remove the corrupted data file
                    files_to_be_removed = glob.glob(os.path.join(base_path, f"{data_file_name}*.bin"))
                    for _file in files_to_be_removed:
                        print(f"Removing file: {_file}")
                        os.remove(_file)

                    exit_current_loop = True
                    
                else:
                    print("Thread finished successfully")
                
                # Thread can still be alive at this point. Do another join without a timeout 
                # to verify thread shutdown.
                # https://stackoverflow.com/questions/34562473/most-pythonic-way-to-kill-a-thread-after-some-period-of-time
                t.join()

                if exit_current_loop:
                    continue
            
            else:

                try:
                    print(f"Taking data with config file: {tmp_config_file}")
                    os.system(f"{self.run_sandyaq_command} -c {tmp_config_file} -n {number_of_events} -d {base_path} -f {data_file_name}")
                except Exception as e:
                    print(f"Error running sandyaq: {e}")
        
            end_timestamp = datetime.datetime.now()

            meta_file_name = os.path.join(base_path, f"meta_{data_file_name}.json")

            # note that the dictionary is assigned by reference, so this will update
            # either self.calib_data_taking_setting or self.data_taking_settings, which
            # is desired, i.e. this is on purpose.
            data_taking_settings["runtime"] = str(end_timestamp - start_timestamp)
            data_taking_settings["start_timestamp"] = str(start_timestamp)
            # retrieve record length from data takking configuration
            tmp_config = configparser.ConfigParser()
            tmp_config.optionxform = str
            tmp_config.read(tmp_config_file)
            data_taking_settings["record_length"] = tmp_config.get("COMMON", "RECORD_LENGTH")
            
            self._metadata_checklist(data_taking_settings)
            with open(meta_file_name, "w") as f:
                json.dump(data_taking_settings, f, indent=4)

            # with open(runtime_csv_file, "a") as f:
            #     f.write(f"{channel},{(end_timestamp - start_timestamp).total_seconds()}\n")
                
        return 
    
if __name__ == "__main__":
    test_config = {}
    test_config["channel_threshold_dict"] = {0:2000,1:2319,2:2618,3:2273,4:2426,5:2341,6:2468,7:2567,8:2801,9:2371,10:2210,11:2352,12:2470,13:2496,14:2602,15:2264,16:2284,17:2531,18:2216,19:2147,20:2522,21:2306,22:2369,23:2465}
    test_config["number_of_events"] = 5000
    test_config["output_folder"] = "./test_calibration"
    test_config["voltage_config"] = {"preamp_1": -49, "preamp_2": -49,"preamp_3": -49,"preamp_4": -49,"preamp_5": -49}
    test_config["temperature"] = -98
    test_config["threshold_multiplier"] = 3.5


    test_calibration = SingleCalibration(test_config, calibration=False)
    test_calibration.run(dry_run=False)

        
        

            


