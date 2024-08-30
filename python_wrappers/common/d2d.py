#!/home/daqtest/anaconda3/bin python

"""
This module read in the dataframe or dictionaries of np.array
- convert them interchangably
- apply masks to all data
- get the length of the table (i.e. how many entries)
"""

import numpy as np
import sys
sys.path.insert(0,"/home/daqtest/Processor/sandpro")
import pandas as pd
import re

sys.path.insert(0,"../")
from dataclasses import dataclass

@dataclass
class data:
    def __init__(self, input: object):
        self.import_data(input)
    
    def import_data(self, df: pd.DataFrame):
        for col_name in df.columns:
            setattr(self, col_name, df[col_name].to_numpy())
            
    def import_data(self, dictionary: dict):
        for var_name in dictionary.keys():
            setattr(self, var_name, np.array(dictionary[var_name]))
    
    def get_df(self):
        df = pd.DataFrame(self.__dict__,index=None)
        return df
    
    def get_dict(self):
        return self.__dict__
            
    def apply_mask(self, mask, inplace = False):
        print("before cut: ", len(self.__dict__['file_path']))
        new_dict = {}
        for i in self.__dict__.keys():
            if inplace:
                self.__dict__[i] = self.__dict__[i][mask]
            else:
                new_dict[i] = self.__dict__[i][mask]
        
        if inplace:   
            first = next(iter(self.__dict__.values()))
            print("after cut: ", len(first))
            return
        else:
            first = next(iter(new_dict.values()))
            print("after cut: ", len(first))
            return run_info_data(new_dict)
        
    def __len__(self):
        # the length of all array should be the same
        # so just picked a random one
        first = next(iter(self.__dict__.values()))
        return len(first)
            
