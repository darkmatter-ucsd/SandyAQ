#include "V1742.hh"

V1742::~V1742() {
    Quit();
}

int V1742::ProgramDigitizers() {
    int ret = 0;
    for (int i = 0; i < m_iNBoards; i++) {
        if (m_sFirmwares[i] == "WAVEFORM") {
            std::cout << "Programming the digitizer with the waveform acquisition firmware\n";
            ret = ProgramDefault(i);
        }
        else {
            std::cout << "ERROR: Firmware not recognized! Options for the V1742 are: 'WAVEFORM'"<<std::endl;
            exit(EXIT_FAILURE);
        }

        if (ret !=0) {
            std::cout << "ERROR: Could not program board " << i << std::endl;
            Quit();
        }
    }

    return ret;
}

void V1742::Quit() {
    for (int i = 0; i < m_iNBoards; i++) {
         /* stop the acquisition */
        // CAEN_DGTZ_SWStopAcquisition(m_iHandles[i]);
        /* close the device and free the buffers */
        // if(Event8[i])    CAEN_DGTZ_FreeEvent(handle[i], (void**)&Event8[i]);
        // if(Event16[i])    CAEN_DGTZ_FreeEvent(handle[i], (void**)&Event16[i]);
        // CAEN_DGTZ_FreeReadoutBuffer(&buffer[i]);
        /* close connection to boards */
        CAEN_DGTZ_CloseDigitizer(m_iHandles[i]);
    }
}

int V1742::ReadX742SpecificParams(){
    inih::INIReader r{ m_sConfigFile };
    int ret = 0;

    for (int i : m_iBoardIndices) {
        std::cout << "BOARD " << i << "\n";
        std::string sBoardCategory = "BOARD-"+std::to_string(i);
        //ENABLED_FAST_TRIGGER_DIGITIZING should have a value of 1 or 0
        m_iFastTriggerDigitizing.push_back(r.Get<uint32_t>(sBoardCategory, "ENABLED_FAST_TRIGGER_DIGITIZING"));
        std::string FastTrgMode = r.Get<std::string>(sBoardCategory, "FAST_TRIGGER");
        m_iFastTriggerEnabled.push_back(TriggerModeMap[FastTrgMode]);
        int iDRS4Freq = r.Get<int>(sBoardCategory, "DRS4_FREQUENCY");
        m_iDRS4Frequency.push_back((CAEN_DGTZ_DRS4Frequency_t) iDRS4Freq);
        m_iRecordLength.push_back(r.Get<uint32_t>(sBoardCategory, "RECORD_LENGTH"));

        std::vector<uint32_t> GroupDCOffset(4);
        std::vector<uint32_t> GroupTriggerThreshold(4);
        for (int j=0; j<2; j++){
            std::string sTRjDCOffset = "TR"+std::to_string(j)+"_DC_OFFSET";
            std::string sTRjTrigThresh = "TR"+std::to_string(j)+"_TRIGGER_THRESHOLD";

            uint32_t iTRjDCOffset = r.Get<uint32_t>(sBoardCategory, sTRjDCOffset);
            uint32_t iTRjTriggerThreshold = r.Get<uint32_t>(sBoardCategory, sTRjTrigThresh);

            GroupDCOffset[2*j] = iTRjDCOffset;
            GroupDCOffset[2*j+1] = iTRjDCOffset;

            GroupTriggerThreshold[2*j] = iTRjTriggerThreshold;
            GroupTriggerThreshold[2*j+1] = iTRjTriggerThreshold;
        }
        m_iGroupDCOffset.push_back(GroupDCOffset);
        m_iGroupTriggerThreshold.push_back(GroupTriggerThreshold);
    }
}

int V1742::ProgramDefault(int BoardNum) {
    int ret = 0;
    int handle = m_iHandles[BoardNum];
    CAEN_DGTZ_BoardInfo_t BoardInfo = m_BoardInfo[BoardNum];

    ret |= CAEN_DGTZ_Reset(handle);
    if (ret != 0) {
        printf("Error: Unable to reset digitizer.\nPlease reset digitizer manually then restart the program\n");
        return -1;
    }

    switch( BoardInfo.FormFactor) {
    case CAEN_DGTZ_VME64_FORM_FACTOR:
    case CAEN_DGTZ_VME64X_FORM_FACTOR:
        m_iNch = 36;
        break;
    case CAEN_DGTZ_DESKTOP_FORM_FACTOR:
    case CAEN_DGTZ_NIM_FORM_FACTOR:
        m_iNch = 16;
        break;
    }

    //Fast trigger digitization and enabling. Unique to 742s
    CAEN_DGTZ_EnaDis_t FTDigiEnable = (CAEN_DGTZ_EnaDis_t) m_iFastTriggerDigitizing[BoardNum];
    ret |= CAEN_DGTZ_SetFastTriggerDigitizing(handle,FTDigiEnable);
    PrintError(BoardNum, "Setting (x742 only)", "fast trigger digitizing", ret);
    ret |= CAEN_DGTZ_SetFastTriggerMode(handle,m_iFastTriggerEnabled[BoardNum]);
    PrintError(BoardNum, "Setting (x742 only)", "fast trigger mode", ret);

    //Record length
    ret |= CAEN_DGTZ_SetRecordLength(handle, m_iRecordLength[BoardNum]);
    PrintError(BoardNum, "Setting", "record length", ret);

    //Post trigger
    ret |= CAEN_DGTZ_SetPostTriggerSize(handle, m_iPostTriggers[BoardNum]);
    PrintError(BoardNum, "Setting", "post trigger", ret);

    //Set FPIOlevel
    CAEN_DGTZ_IOLevel_t FPIOlevel = CAEN_DGTZ_IOLevel_NIM;
    if(m_sFPIOLevel[BoardNum] == "NIM"){FPIOlevel = CAEN_DGTZ_IOLevel_NIM;}
    else if (m_sFPIOLevel[BoardNum] == "TTL"){FPIOlevel = CAEN_DGTZ_IOLevel_TTL;}
    else {std::cout<<"Wrong Input for FPIOlevel. Use 'NIM' or 'TTL'. Default: 'NIM'"<<std::endl;}
    ret |= CAEN_DGTZ_SetIOLevel(handle, FPIOlevel);
    PrintError(BoardNum, "Setting", "FPIOlevel", ret);

    ret |= CAEN_DGTZ_SetMaxNumEventsBLT(handle, m_CommonConfig.uiNumEventsBLT);
    ret |= CAEN_DGTZ_SetAcquisitionMode(handle, CAEN_DGTZ_SW_CONTROLLED); //Start and stop acquisition is issued by software command.
    
    //Set ExtTriggerInputMode
    //TODO: add Veto mode
    ret |= CAEN_DGTZ_SetExtTriggerInputMode(handle, m_iExternalTriggerEnabled[BoardNum]);
    PrintError(BoardNum, "Setting", "ExtTriggerInputMode", ret);

    //Channel group enabling. x742 specific settings
    ret |= CAEN_DGTZ_SetGroupEnableMask(handle, m_iEnableMask[BoardNum]);
    ret |= CAEN_DGTZ_SetDRS4SamplingFrequency(handle, m_iDRS4Frequency[BoardNum]);
    for(int i=0; i<(m_iNChannels[BoardNum]/8); i++) {
        if (m_iEnableMask[BoardNum] & (1<<i)) {
            if (BoardInfo.FamilyCode == CAEN_DGTZ_XX742_FAMILY_CODE) {
                for(int j=0; j<8; j++) {
                    ret |= CAEN_DGTZ_SetChannelDCOffset(handle, (i * 8) + j, m_iChannelDCOffset[BoardNum][i]);
                }
            }
            CAEN_DGTZ_TriggerPolarity_t TrigPol = (CAEN_DGTZ_TriggerPolarity_t) m_iPulsePolarity[BoardNum][i];
            ret |= CAEN_DGTZ_SetTriggerPolarity(handle, i, TrigPol); //.TriggerEdge
            ret |= CAEN_DGTZ_SetGroupFastTriggerDCOffset(handle,i,m_iGroupDCOffset[BoardNum][i]);
            ret |= CAEN_DGTZ_SetGroupFastTriggerThreshold(handle,i,m_iGroupTriggerThreshold[BoardNum][i]);
        }
    }

    return ret;
}

