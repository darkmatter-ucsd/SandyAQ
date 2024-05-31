from typing import List
import os
import glob
import pandas as pd
import json
import re

DATA_FOLDERS = [
    "../data",
    # Add more data folders as needed
]

RUN_INFO_FILE = "run_info.csv"

def get_data_files(data_directories: List[str]) -> List[str]:
    """
    Get all the data files in the given data directories
    Also search subdirectories
    """
    data_files = []
    for data_directory in data_directories:
        data_files.extend(glob.glob(os.path.join(data_directory, "**/config_*.bin"), recursive=True))
    return data_files

def data_files_to_dataframe(data_files: List[str], existing_df: pd.DataFrame = None) -> pd.DataFrame:
    """
    Convert the list of data files into a dataframe
    - extract date, channel, threshold from the file name 
    - attach the information to the dataframe
    - sort the dataframe by date and assign run_id
    - find the corresponding meta file
    - read voltage, temperature from the meta file
    """
    data = []
    for data_file in data_files:
        # Check if the data file is already in the existing DataFrame
        if existing_df is not None and data_file in existing_df["file_path"].values:
            continue

        # Extract date, channel, threshold from the file name
        file_name = os.path.basename(data_file)
        match = re.match(r"config_(\d+)_(\d+)_(\d{8})_(\d{6})_board_(\d+)\.bin", file_name)
        if match:
            channel, threshold, date, time, board = match.groups()
            channel = int(channel)
            board = int(board)
            
            # Check if the run is valid based on the channel and board combination
            if (0 <= channel <= 15 and board == 0) or (channel > 15 and board == 1):
                date_time = pd.to_datetime(f"{date}_{time}", format="%Y%m%d_%H%M%S")
                
                # Find the corresponding meta file
                meta_file = os.path.join(os.path.dirname(data_file), f"meta_config_{channel}_{threshold}_{date}_{time}_board_{board}.json")
                
                # Read voltage and temperature from the meta file
                voltage = None
                temperature = None
                comment = None
                number_of_events = None
                if os.path.exists(meta_file):
                    with open(meta_file, "r") as file:
                        meta_data = json.load(file)
                        voltage_config = meta_data.get("voltage_config")
                        if voltage_config:
                            voltage = list(voltage_config.values())[0]  # Assume all preamps have the same voltage
                        temperature = meta_data.get("temperature")
                        comment = meta_data.get("comment")
                        number_of_events = meta_data.get("number_of_events")
                
                data.append({
                    "file_path": data_file,
                    "channel": channel,
                    "threshold": int(threshold),
                    "date_time": date_time,
                    "board": board,
                    "voltage": voltage,
                    "temperature": temperature,
                    "comment": comment,
                    "number_of_events": number_of_events
                })
    
    # Create a DataFrame from the new data
    new_df = pd.DataFrame(data)
    
    if existing_df is not None:
        # Concatenate the existing DataFrame with the new DataFrame
        df = pd.concat([existing_df, new_df], ignore_index=True)
    else:
        df = new_df
    
    # Sort the DataFrame by date and assign run_id
    df.sort_values("date_time", inplace=True)
    df.reset_index(drop=True, inplace=True)
    df["run_id"] = df.index + 1
    
    return df

def main():
    # Load the existing run_info DataFrame if it exists
    if os.path.exists(RUN_INFO_FILE):
        run_info_df = pd.read_csv(RUN_INFO_FILE)
    else:
        run_info_df = None

    # Get the list of data files from DATA_FOLDERS
    data_files = get_data_files(DATA_FOLDERS)

    # Generate the updated run_info DataFrame
    updated_run_info_df = data_files_to_dataframe(data_files, existing_df=run_info_df)

    # Save the updated run_info DataFrame to RUN_INFO_FILE
    updated_run_info_df.to_csv(RUN_INFO_FILE, index=False)

    print("Run info DataFrame updated and saved to", RUN_INFO_FILE)

if __name__ == "__main__":
    main()