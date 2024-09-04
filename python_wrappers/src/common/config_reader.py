"""
    This class read common_config.ini and retrieve all common configurations
    and paths to other configuration files.
    
    The path between config/ and this script is relative. So if directory moved, 
    it will return errors. Please update the relative path

Raises:
    FileNotFoundError: common_config.ini not found
    FileNotFoundError: other configs not found

Returns:
    
"""

import configparser
import os

class ConfigurationReader:
    def __init__(self):
        """
        Initialize the ConfigurationReader with the path to the shared configuration file.
        """
        
        ### Get the absolute path to the config directory
        
        # abs path to this script
        current_dir = os.path.dirname(os.path.abspath(__file__))
        
        # path from this script to config/, please update this if error occurs
        # other configuration files also rely on this path
        self.config_dir = os.path.join(current_dir, "../../config/")
        common_config_path = os.path.join(self.config_dir, "common_config.ini")
        
        # check if common_config.ini exist
        if os.path.isfile(common_config_path):
            self.common_config_path = common_config_path
            self.config = configparser.ConfigParser()
            self.config.optionxform = str # preserve case
            self.config.read(self.common_config_path)
        else:
            raise FileNotFoundError(f"{common_config_path} does not exist.")
        
    def load_config(self, file_path):
        """
        Load and return a configuration from a specified file path.
        """
        # if the path is not absolute, add the absolute path of 
        # the config/ dir
        if os.path.isabs(file_path) == False:
            file_path = os.path.join(self.config_dir,file_path)
        
        # check if the .ini exist
        if os.path.isfile(file_path):
            cfg = configparser.ConfigParser()
            cfg.optionsxform = str # preserve case
            cfg.read(file_path)
        else:
            raise FileNotFoundError(f"{file_path} does not exist.")
        
        return cfg

    def get_path(self,file_path):
        if os.path.isabs(file_path) == False:
            file_path = os.path.join(self.config_dir,file_path)
        return file_path
    
    def get_data_taking_config(self):
        path = self.config.get('CONFIG_PATHS', 'data_taking_config')
        return self.load_config(path)

    def get_data_processing_config(self):
        path = self.config.get('CONFIG_PATHS', 'data_processing_config')
        return self.load_config(path)
    
    def get_gain_analysis_config(self):
        path = self.config.get('CONFIG_PATHS', 'gain_analysis_config')
        return self.load_config(path)
    
    def get_sandpro_process_config(self):
        path = self.config.get('PRIVATE_CONFIG_PATHS', 'sandpro_process_config')
        return self.load_config(path)
    
    def get_sandpro_process_config_path(self):
        path = self.config.get('PRIVATE_CONFIG_PATHS', 'sandpro_process_config')
        return self.get_path(path)
    
    def get_tmp_process_config(self):
        path = self.config.get('PRIVATE_CONFIG_PATHS', 'tmp_process_config')
        return self.load_config(path)


# if __name__ == "__main__":
#     # Create a ConfigReader instance
#     config_reader = ConfigurationReader()

#     # Access configurations
#     data_taking_config = config_reader.get_data_taking_config()
#     data_processing_config = config_reader.get_data_processing_config()
#     resource_directory = config_reader.get_resource_directory()
#     default_analysis_mode = config_reader.get_default_analysis_mode()

#     print("Data Taking Config:", data_taking_config.sections())
#     print("Data Processing Config:", data_processing_config.sections())
#     print("Resource Directory:", resource_directory)
#     print("Default Analysis Mode:", default_analysis_mode)