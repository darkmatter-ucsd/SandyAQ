#include "V1725.hh"

V1725::V1725(std::string& sConfigFile, CommonConfig_t &CommonConfig, int iBoardStart) {
    inih::INIReader r{ sConfigFile };
    int ret = 0;

    m_CommonConfig = CommonConfig;
    for (const std::string& n : m_CommonConfig.sBoardTypes) {
        if (n == "V1725") m_iNBoards++;
    }

    for (int i = iBoardStart; i < m_iNBoards+iBoardStart; i++){
        std::string sBoardCategory = "BOARD-"+std::to_string(i);


        m_iNChannels[i] = r.Get<uint32_t>(sBoardCategory, "N_CHANNELS");
        m_iPostTriggers[i] = r.Get<uint32_t>(sBoardCategory, "POST_TRIGGER");
        m_sFirmwares.push_back(r.Get<std::string>(sBoardCategory, "FIRMWARE"));
        m_sLinkTypes.push_back(r.Get<std::string>(sBoardCategory, "OPEN"));

        std::vector<std::string> sLinkValues = r.GetVector<std::string>(sBoardCategory, "OPEN_VALUES");
        std::vector<uint32_t> iLinkValues;
        for (const std::string &s : sLinkValues) {
            iLinkValues.push_back(std::stoi(s, nullptr, 16));
        }
        // m_iLinkValues.push_back(r.GetVector<uint32_t>(sBoardCategory, "OPEN_VALUES"));
        m_iLinkValues.push_back(iLinkValues);
        m_iOpenChannels.push_back(r.GetVector<uint32_t>(sBoardCategory, "CHANNEL_LIST"));
        m_iCoincidences[i] = r.Get<uint32_t>(sBoardCategory, "COINCIDENCE");
        // m_iPulsePolarity[i] = r.Get<uint32_t>(sBoardCategory, "PULSE_POLARITY");
        m_iETTT[i] = r.Get<uint32_t>(sBoardCategory, "EXTENDED_TTT");
        std::string ExtTrgMode = r.Get<std::string>(sBoardCategory, "EXTERNAL_TRIGGER");
        m_iExternalTriggerEnabled.push_back(TriggerModeMap[ExtTrgMode]);
        m_sFPIOLevel.push_back(r.Get<std::string>(sBoardCategory, "FPIO_LEVEL"));

        m_iEnableMask[i] = 0;

        std::vector<uint32_t> iDCOffsets;
        std::vector<uint32_t> iTriggerThresholds;
        std::vector<CAEN_DGTZ_TriggerMode_t> sTriggerSettings;
        std::vector<uint32_t> iPulsePolarity;
        for (const uint32_t ch : m_iOpenChannels[i]) {
            std::string sBoardChannel = sBoardCategory+"_CHANNEL-"+std::to_string(ch);
            m_iEnableMask[i] += 1 << ch;
            int iDCValue = r.Get<int>(sBoardChannel, "DC_OFFSET");
            iDCValue = (int)((iDCValue + 50) * 65535 / 100);
            iDCOffsets.push_back(iDCValue);

            uint32_t iTrigThresh = r.Get<uint32_t>(sBoardChannel, "TRIGGER_THRESHOLD");
            iTriggerThresholds.push_back(iTrigThresh);

            std::string sTrigSet = r.Get<std::string>(sBoardChannel, "CHANNEL_TRIGGER");
            sTriggerSettings.push_back(TriggerModeMap[sTrigSet]);

            iPulsePolarity.push_back(r.Get<uint32_t>(sBoardChannel, "PULSE_POLARITY"));
        }
        m_iChannelDCOffset.push_back(iDCOffsets);
        m_iTriggerThresholds.push_back(iTriggerThresholds);
        m_sChannelTriggerSetting.push_back(sTriggerSettings);
        m_iPulsePolarity.push_back(iPulsePolarity);
    }

    ret = OpenDigitizers();
}

V1725::~V1725() {
    Quit();
}

int V1725::ProgramDigitizers() {
    int ret = 0;
    for (int i = 0; i < m_iNBoards; i++) {
        if (m_sFirmwares[i] == "WAVEFORM") {
            ret = ProgramDefault(i);
        }
        else if (m_sFirmwares[i] == "DAW") {
            ret = ProgramDAW(i);
        }
        else {
            std::cout << "ERROR: Firmware not recognized! Options are: 'WAVEFORM' or 'DAW'"<<std::endl;
            exit(EXIT_FAILURE);
        }

        if (ret !=0) {
            std::cout << "ERROR: Could not program board " << i << std::endl;
            Quit();
        }
    }

    return ret;
}

void V1725::Quit() {
    for (int i = 0; i < m_iNBoards; i++) {
         /* stop the acquisition */
        CAEN_DGTZ_SWStopAcquisition(m_iHandles[i]);
        /* close the device and free the buffers */
        // if(Event8[i])    CAEN_DGTZ_FreeEvent(handle[i], (void**)&Event8[i]);
        // if(Event16[i])    CAEN_DGTZ_FreeEvent(handle[i], (void**)&Event16[i]);
        // CAEN_DGTZ_FreeReadoutBuffer(&buffer[i]);
        /* close connection to boards */
        CAEN_DGTZ_CloseDigitizer(m_iHandles[i]);
    }
}

int V1725::OpenDigitizers() {
    int ret = 0;

    for (int BoardNum = 0; BoardNum < m_iNBoards; BoardNum++) {
        int handle;

        CAEN_DGTZ_ConnectionType iLinkType;
        int iLinkNum;
        int iConetNode;
        uint32_t iBaseAddress;

        if (m_sLinkTypes[BoardNum] == "USB") {
            iLinkType = CAEN_DGTZ_USB;
        }
        else if (m_sLinkTypes[BoardNum] == "PCI") {
            iLinkType = CAEN_DGTZ_OpticalLink;
        }
        else if (m_sLinkTypes[BoardNum] == "USB_A4818") {
            iLinkType = CAEN_DGTZ_USB_A4818;
        }
        else if (m_sLinkTypes[BoardNum] == "USB_A4818_V2718") {
            iLinkType = CAEN_DGTZ_USB_A4818_V2718;
        }
        else if (m_sLinkTypes[BoardNum] == "USB_A4818_V3718") {
            iLinkType = CAEN_DGTZ_USB_A4818_V3718;
        }
        else if (m_sLinkTypes[BoardNum] == "USB_A4818_V4718") {
            iLinkType = CAEN_DGTZ_USB_A4818_V4718;
        }
        else if (m_sLinkTypes[BoardNum] == "USB_V4718") {
            iLinkType = CAEN_DGTZ_USB_V4718;
        }
        else{
            std::cout << "ERROR: Invalid link type" <<std::endl;
            exit(EXIT_FAILURE);
        }
        
        //Open the digitizer
        ret = CAEN_DGTZ_OpenDigitizer(iLinkType, m_iLinkValues[BoardNum][0], m_iLinkValues[BoardNum][1], m_iLinkValues[BoardNum][2], &handle);
        m_iHandles[BoardNum] = handle;
        if (ret) {
            std::cout << "ERROR: Can't open digitizer " << BoardNum << std::endl;
            Quit();
        }

        //Get the board info
        CAEN_DGTZ_BoardInfo_t BoardInfo;
        ret = CAEN_DGTZ_GetInfo(handle, &BoardInfo);
        m_BoardInfo[BoardNum] = BoardInfo;
        if (ret) {
            std::cout << "ERROR: Can't get the board info for digitizer " << BoardNum << std::endl;
            Quit();
        }

        //See if the PLL has been unlocked
        ret = CheckBoardFailureStatus(handle, BoardInfo);
        if (ret) {
            std::cout << "ERROR: PLL has been unlocked" << std::endl;
            Quit();
        }

        m_bOpen[BoardNum] = true;
    }

    return ret;
}

//Default Wavedump
int V1725::ProgramDefault(int BoardNum) {
    int ret = 0;
    int handle = m_iHandles[BoardNum];
    CAEN_DGTZ_BoardInfo_t BoardInfo = m_BoardInfo[BoardNum];

    ret |= CAEN_DGTZ_Reset(handle);
    if (ret != 0) {
        printf("Error: Unable to reset digitizer.\nPlease reset digitizer manually then restart the program\n");
        return -1;
    }

    //Set record length
    ret |= CAEN_DGTZ_SetRecordLength(handle, m_CommonConfig.uiRecordLength);
    PrintError(BoardNum, "Setting", "record length", ret);
    ret |= CAEN_DGTZ_GetRecordLength(handle, &m_CommonConfig.uiRecordLength);

    //Set post trigger
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
    // CAEN_DGTZ_TriggerMode_t TrigMode = CAEN_DGTZ_TRGMODE_ACQ_ONLY;
    // if(m_iExternalTriggerEnabled[BoardNum] == "DISABLED"){TrigMode = CAEN_DGTZ_TRGMODE_DISABLED;}
    // else if(m_iExternalTriggerEnabled[BoardNum] == "ACQUISITION_ONLY"){TrigMode = CAEN_DGTZ_TRGMODE_ACQ_ONLY;}
    // else if(m_iExternalTriggerEnabled[BoardNum] == "ACQUISITION_AND_TRGOUT"){TrigMode = CAEN_DGTZ_TRGMODE_ACQ_AND_EXTOUT;}
    // ret |= CAEN_DGTZ_SetExtTriggerInputMode(handle, TrigMode);
    ret |= CAEN_DGTZ_SetExtTriggerInputMode(handle, m_iExternalTriggerEnabled[BoardNum]);
    PrintError(BoardNum, "Setting", "ExtTriggerInputMode", ret);

    //Program the channels
    ret |= CAEN_DGTZ_SetChannelEnableMask(handle, m_iEnableMask[BoardNum]);
    PrintError(BoardNum, "Setting", "ChannelEnableMask", ret);
    for (int c = 0; c < m_iOpenChannels[BoardNum].size(); c++){
        int ch = m_iOpenChannels[BoardNum][c];
        CAEN_DGTZ_TriggerPolarity_t TriggerPolarity;
        if (m_iPulsePolarity[BoardNum][c] == 1) {TriggerPolarity = CAEN_DGTZ_TriggerOnRisingEdge;} //Rising edge for pos pulse
        else {TriggerPolarity = CAEN_DGTZ_TriggerOnFallingEdge;} //Falling edge for neg pulse

        ret |= CAEN_DGTZ_SetChannelDCOffset(handle, ch, m_iChannelDCOffset[BoardNum][c]);
        PrintError(BoardNum, "Setting", "ChannelDCOffset", ret);

        ret |= CAEN_DGTZ_SetChannelTriggerThreshold(handle, ch, m_iTriggerThresholds[BoardNum][c]);
        PrintError(BoardNum, "Setting", "ChannelTriggerThreshold", ret);

        ret |= CAEN_DGTZ_SetTriggerPolarity(handle, ch, TriggerPolarity);
        PrintError(BoardNum, "Setting", "ChannelTriggerPolarity", ret);
    
    }

    //Special pair settings for the V1725/30
    for (int c = 0; c < m_iNChannels[BoardNum]; c+=2) {
        if (m_iEnableMask[BoardNum] & (0x3<<c)) { //If either channel c or channel c+1 is enabled
            CAEN_DGTZ_TriggerMode_t modes[2];
            CAEN_DGTZ_TriggerMode_t couple_mode;
            uint32_t pair_chmask = 0;

            for (int j = 0; j < 2; j++){
                if ((m_iEnableMask[BoardNum] & (1<<(c+j)))>>(c+j)) modes[j] = m_sChannelTriggerSetting[BoardNum][c+j];
                else modes[j] = CAEN_DGTZ_TRGMODE_DISABLED;
            }

            if (modes[0] != CAEN_DGTZ_TRGMODE_DISABLED) {
                if (modes[1] == CAEN_DGTZ_TRGMODE_DISABLED)
                    pair_chmask = (0x1 << c);
                else
                    pair_chmask = (0x3 << c);
                
                couple_mode = modes[0];
            }
            else{
                couple_mode = modes[1];
                pair_chmask = (0x2 << c);
            }

            pair_chmask &= m_iEnableMask[BoardNum];

            ret |= CAEN_DGTZ_SetChannelSelfTrigger(handle, couple_mode, pair_chmask);
            PrintError(BoardNum, "Setting", "ChannelSelfTriggerMode", ret);

        }
    }

    //Read the Register for the Trigger
    uint32_t global_trigger_reg_data, fpio_reg_data, lvds_reg_data, acq_ctrl_reg_data, board_config_reg_data;

    ret |= CAEN_DGTZ_ReadRegister(handle, 0x810C, &global_trigger_reg_data);
    PrintError(BoardNum, "Reading", "Register[0x810c]", ret);
    ret |= CAEN_DGTZ_WriteRegister(handle, 0x810C, (global_trigger_reg_data|(m_iCoincidences[BoardNum]<<24)));
    PrintError(BoardNum, "Writing", "Register[0x810c]", ret);

    //Enable extended trigger time tag
	// ret |= CAEN_DGTZ_ReadRegister(handle, 0x811C, &fpio_reg_data);
	// ret |= CAEN_DGTZ_WriteRegister(handle, 0x811C, ((fpio_reg_data)|(1<<22)));


    ret |= CAEN_DGTZ_ReadRegister(handle, 0x810C, &global_trigger_reg_data);
    PrintError(BoardNum, "Reading", "Register[0x810c]", ret);

    ret |= CAEN_DGTZ_ReadRegister(handle, 0x81A0, &lvds_reg_data);
    PrintError(BoardNum, "Reading", "Register[0x81A0]", ret);

    ret |= CAEN_DGTZ_ReadRegister(handle, 0x8100, &acq_ctrl_reg_data);
    PrintError(BoardNum, "Reading", "Register[0x8100]", ret);

    ret |= CAEN_DGTZ_ReadRegister(handle, 0x811C, &fpio_reg_data);
    PrintError(BoardNum, "Reading", "Register[0x811c]", ret);

    ret |= CAEN_DGTZ_ReadRegister(handle, 0x8000, &board_config_reg_data);
    PrintError(BoardNum, "Reading", "Register[0x8000]", ret);

    printf("----------Board[%u]----------\n", BoardNum);
    printf("Global trigger register: %u\n", global_trigger_reg_data);
    printf("FPIO Register: %u\n", fpio_reg_data);
    printf("LVDS Register: %u\n", lvds_reg_data);
    printf("Acquisition Control Register: %u\n", acq_ctrl_reg_data);
    printf("Board Configuration Register: %u\n", board_config_reg_data);
    printf("Coincidence level: %u\n", m_iCoincidences[BoardNum]);

    if (ret)/* Get time in milliseconds from the computer internal clock */
        printf("Warning: errors found during the programming of the digitizer(Board[%u]).\nSome settings may not be executed\n", BoardNum);

    // return 0;

    return ret;
};



// int V1725::StopRun(int *handle){
    
// }
//DAW
int V1725::ProgramDAW(int BoardNum) {};
